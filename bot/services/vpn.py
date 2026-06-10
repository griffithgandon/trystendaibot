"""
Сервис работы с 3X-UI панелью (VLESS + Hysteria2).

Портирован с синхронного requests-кода на async aiohttp.
Каждая публичная функция открывает свою ClientSession.
"""

import json
import logging
import ssl as ssl_module
import time
from uuid import uuid4

import aiohttp

from bot.config import get_settings
from bot.database.repo import get_username

logger = logging.getLogger(__name__)
settings = get_settings()

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


# ===== Низкоуровневые помощники =====

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "Accept": "application/json",
    }


def _ssl_param() -> bool | ssl_module.SSLContext:
    """
    Преобразует settings.ssl_verify (True|False|"/path/to/cert")
    в значение, понятное aiohttp (ssl=):
      True  -> True  (проверка по умолчанию)
      False -> False (проверка отключена)
      path  -> SSLContext с указанным CA
    """
    v = settings.ssl_verify
    if v is True:
        return True
    if v is False:
        return False
    return ssl_module.create_default_context(cafile=v)


_SSL = _ssl_param()


def _new_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers=_headers(), timeout=REQUEST_TIMEOUT)


async def _request(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    json_data: dict | None = None,
) -> tuple[int, dict | None, str]:
    """Выполняет запрос, возвращает (status, parsed_json_or_None, raw_text)."""
    async with session.request(method, url, json=json_data, ssl=_SSL) as resp:
        text = await resp.text()
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            data = None
        return resp.status, data, text


def _ok(status: int, data: dict | None) -> bool:
    return status == 200 and data is not None and data.get("success") is True


# ===== GET INBOUNDS =====

async def get_inbounds() -> dict | None:
    try:
        async with _new_session() as session:
            status, data, _ = await _request(
                session, "GET", f"{settings.panel_url}/panel/api/inbounds/list"
            )
            if status != 200:
                logger.error("LIST ERROR STATUS: %s", status)
                return None
            return data
    except Exception as e:
        logger.error("LIST ERROR: %s", e)
        return None


# ===== INBOUND DISCOVERY =====

def _discover_ids(data: dict) -> tuple[list[int], int]:
    """Извлекает (vless_ids, hysteria_id) из ответа /inbounds/list."""
    vless_ids: list[int] = []
    hysteria_id = 0

    for inbound in data.get("obj", []):
        protocol = inbound.get("protocol", "").lower()
        inbound_id = inbound.get("id")
        if inbound_id is None:
            continue
        if protocol == "vless":
            vless_ids.append(inbound_id)
        elif protocol in ("hysteria2", "hysteria") and not hysteria_id:
            hysteria_id = inbound_id

    return vless_ids, hysteria_id


async def resolve_inbound_ids() -> tuple[list[int], int]:
    """
    Возвращает (vless_inbound_ids, hysteria_inbound_id).

    Значения из .env имеют приоритет (ручной override); чего не хватает —
    автоматически определяется с панели по протоколу инбаунда.
    """
    vless_ids = settings.vless_inbound_ids
    hysteria_id = settings.hysteria_inbound_id

    need_hysteria = settings.hysteria_enabled and not hysteria_id
    if vless_ids and not need_hysteria:
        return vless_ids, hysteria_id

    data = await get_inbounds()
    if not data:
        logger.error("DISCOVERY: панель недоступна, использую значения из .env")
        return vless_ids, hysteria_id

    found_vless, found_hysteria = _discover_ids(data)
    if not vless_ids:
        vless_ids = found_vless
        logger.info("DISCOVERY: VLESS inbound ids с панели: %s", vless_ids)
    if not hysteria_id:
        hysteria_id = found_hysteria
        if settings.hysteria_enabled:
            logger.info("DISCOVERY: Hysteria inbound id с панели: %s", hysteria_id)

    return vless_ids, hysteria_id


# ===== CREATE USER =====

async def create_user(user_id: int, days: int) -> bool:
    logger.info("CREATE USER: %s", user_id)

    expire = int((time.time() + days * 86400) * 1000)
    username = await get_username(user_id) or f"user_{user_id}"

    sub_id = str(uuid4()).replace("-", "")[:16]
    success = False

    vless_ids, hy_id = await resolve_inbound_ids()
    if not vless_ids:
        logger.error(
            "CREATE USER %s: нет VLESS-инбаундов (ни в .env, ни на панели)", user_id
        )

    async with _new_session() as session:
        # ===== VLESS =====
        vless_uuid = str(uuid4())

        for inbound_id in vless_ids:
            vless_client = {
                "id": vless_uuid,
                "flow": "xtls-rprx-vision",
                "email": f"{user_id}_vless_{inbound_id}",
                "enable": True,
                "expiryTime": expire,
                "limitIp": 1,
                "totalGB": 0,
                "subId": sub_id,
                "comment": username,
            }
            vless_payload = {
                "id": inbound_id,
                "settings": json.dumps({"clients": [vless_client]}),
            }

            try:
                status, data, text = await _request(
                    session,
                    "POST",
                    f"{settings.panel_url}/panel/api/inbounds/addClient",
                    vless_payload,
                )
                logger.info("VLESS [%s] STATUS: %s %s", inbound_id, status, text)
                if _ok(status, data):
                    success = True
            except Exception as e:
                logger.error("VLESS [%s] ERROR: %s", inbound_id, e)

        # ===== HYSTERIA2 =====
        if settings.hysteria_enabled and not hy_id:
            logger.error(
                "HYSTERIA SKIP: включена, но inbound не найден "
                "(ни в .env, ни на панели)"
            )
        elif settings.hysteria_enabled:
            try:
                status, data, text = await _request(
                    session,
                    "GET",
                    f"{settings.panel_url}/panel/api/inbounds/get/{hy_id}",
                )
                logger.info("HYSTERIA GET STATUS: %s", status)

                if not _ok(status, data):
                    logger.error("HYSTERIA GET ERROR: %s", text)
                else:
                    assert data is not None  # гарантируется _ok()
                    inbound_data = data["obj"]
                    settings_obj = json.loads(inbound_data.get("settings", "{}"))
                    clients = settings_obj.get("clients", [])

                    clients.append(
                        {
                            "password": str(uuid4()),
                            "email": f"{user_id}_hy2",
                            "enable": True,
                            "expiryTime": expire,
                            "limitIp": 1,
                            "totalGB": 0,
                            "subId": sub_id,
                            "comment": username,
                        }
                    )
                    settings_obj["clients"] = clients
                    inbound_data["settings"] = json.dumps(settings_obj)

                    status2, data2, text2 = await _request(
                        session,
                        "POST",
                        f"{settings.panel_url}/panel/api/inbounds/update/{hy_id}",
                        inbound_data,
                    )
                    logger.info("HYSTERIA UPDATE STATUS: %s %s", status2, text2)
                    if _ok(status2, data2):
                        success = True
            except Exception as e:
                logger.error("HYSTERIA ERROR: %s", e)
        else:
            logger.info("HYSTERIA SKIP: HYSTERIA_ENABLED=False")

    return success


# ===== Внутренний помощник: обход inbound'ов с мутацией клиентов =====

async def _mutate_clients(user_id: int, mutate, log_prefix: str) -> bool:
    """
    Универсальный обход всех inbound'ов панели.

    `mutate(client) -> bool` модифицирует клиента на месте и возвращает True,
    если изменение нужно сохранить. Используется для enable/disable/extend.

    Возвращает True, если хотя бы одно сохранение прошло успешно.
    """
    data = await get_inbounds()
    if not data:
        return False

    success = False

    async with _new_session() as session:
        for inbound in data.get("obj", []):
            inbound_id = inbound.get("id")
            protocol = inbound.get("protocol", "").lower()

            # ── Hysteria2: правим через get/update всего inbound'а ──
            if protocol in ("hysteria2", "hysteria"):
                try:
                    status, full, text = await _request(
                        session,
                        "GET",
                        f"{settings.panel_url}/panel/api/inbounds/get/{inbound_id}",
                    )
                    if not _ok(status, full):
                        logger.error(
                            "%s HY2 GET [%s] ERROR: %s", log_prefix, inbound_id, text
                        )
                        continue

                    assert full is not None  # гарантируется _ok()
                    full_inbound = full["obj"]
                    full_settings = json.loads(full_inbound.get("settings", "{}"))

                    updated = False
                    for c in full_settings.get("clients", []):
                        if c.get("email", "").startswith(str(user_id)):
                            if mutate(c):
                                updated = True

                    if not updated:
                        continue

                    full_inbound["settings"] = json.dumps(full_settings)

                    status2, data2, text2 = await _request(
                        session,
                        "POST",
                        f"{settings.panel_url}/panel/api/inbounds/update/{inbound_id}",
                        full_inbound,
                    )
                    logger.info(
                        "%s HY2 [%s] STATUS: %s %s",
                        log_prefix, inbound_id, status2, text2,
                    )
                    if _ok(status2, data2):
                        success = True
                except Exception as e:
                    logger.error("%s HY2 [%s] ERROR: %s", log_prefix, inbound_id, e)

            # ── VLESS / VMess: правим через updateClient ──
            else:
                try:
                    cfg = json.loads(inbound.get("settings", "{}"))
                except Exception as e:
                    logger.error("SETTINGS JSON ERROR: %s", e)
                    continue

                targets = [
                    c
                    for c in cfg.get("clients", [])
                    if c.get("email", "").startswith(str(user_id))
                ]
                if not targets:
                    continue

                for client in targets:
                    client_id = client.get("id")
                    if not client_id:
                        continue
                    if not mutate(client):
                        continue

                    payload = {
                        "id": inbound_id,
                        "settings": json.dumps({"clients": [client]}),
                    }
                    try:
                        status, data2, text = await _request(
                            session,
                            "POST",
                            f"{settings.panel_url}/panel/api/inbounds/updateClient/{client_id}",
                            payload,
                        )
                        logger.info(
                            "%s VLESS [%s] STATUS: %s %s",
                            log_prefix, inbound_id, status, text,
                        )
                        if _ok(status, data2):
                            success = True
                    except Exception as e:
                        logger.error(
                            "%s VLESS [%s] ERROR: %s", log_prefix, inbound_id, e
                        )

    return success


# ===== DISABLE USER =====
# Отключает клиента (enable=false) без удаления. Истечение подписки.
async def disable_user(user_id: int) -> bool:
    logger.info("DISABLE USER: %s", user_id)

    def _disable(client: dict) -> bool:
        client["enable"] = False
        return True

    return await _mutate_clients(user_id, _disable, "DISABLE")


# ===== ENABLE USER =====
# Включает клиента обратно (enable=true). Продление если был отключён.
async def enable_user(user_id: int) -> bool:
    logger.info("ENABLE USER: %s", user_id)

    def _enable(client: dict) -> bool:
        client["enable"] = True
        return True

    return await _mutate_clients(user_id, _enable, "ENABLE")


# ===== EXTEND USER =====
# Продлевает подписку и включает клиента обратно.
async def extend_user(user_id: int, days: int) -> bool:
    logger.info("EXTEND USER: %s", user_id)

    now_ms = int(time.time() * 1000)
    add_ms = days * 86400 * 1000

    def _extend(client: dict) -> bool:
        current = client.get("expiryTime", 0)
        client["expiryTime"] = (
            current + add_ms if current > now_ms else now_ms + add_ms
        )
        client["enable"] = True  # при продлении всегда включаем
        return True

    return await _mutate_clients(user_id, _extend, "EXTEND")


# ===== DELETE USER =====
# Полное удаление клиента с панели.
async def delete_user(user_id: int) -> bool:
    logger.info("DELETE USER: %s", user_id)

    data = await get_inbounds()
    if not data:
        return False

    success = False

    async with _new_session() as session:
        for inbound in data.get("obj", []):
            inbound_id = inbound.get("id")
            protocol = inbound.get("protocol", "").lower()

            # ── Hysteria2: удаляем клиента из settings и обновляем inbound ──
            if protocol in ("hysteria2", "hysteria"):
                try:
                    status, full, text = await _request(
                        session,
                        "GET",
                        f"{settings.panel_url}/panel/api/inbounds/get/{inbound_id}",
                    )
                    if not _ok(status, full):
                        logger.error("DELETE HY2 GET [%s] ERROR: %s", inbound_id, text)
                        continue

                    assert full is not None  # гарантируется _ok()
                    full_inbound = full["obj"]
                    full_settings = json.loads(full_inbound.get("settings", "{}"))

                    before = full_settings.get("clients", [])
                    after = [
                        c
                        for c in before
                        if not c.get("email", "").startswith(str(user_id))
                    ]
                    if len(before) == len(after):
                        continue

                    full_settings["clients"] = after
                    full_inbound["settings"] = json.dumps(full_settings)

                    status2, data2, text2 = await _request(
                        session,
                        "POST",
                        f"{settings.panel_url}/panel/api/inbounds/update/{inbound_id}",
                        full_inbound,
                    )
                    logger.info(
                        "DELETE HY2 UPDATE [%s] STATUS: %s %s",
                        inbound_id, status2, text2,
                    )
                    if _ok(status2, data2):
                        success = True
                except Exception as e:
                    logger.error("DELETE HY2 [%s] ERROR: %s", inbound_id, e)

            # ── VLESS / VMess: delClient ──
            else:
                try:
                    cfg = json.loads(inbound.get("settings", "{}"))
                except Exception as e:
                    logger.error("SETTINGS JSON ERROR: %s", e)
                    continue

                targets = [
                    c
                    for c in cfg.get("clients", [])
                    if c.get("email", "").startswith(str(user_id))
                ]
                for client in targets:
                    client_id = client.get("id")
                    if not client_id:
                        continue
                    try:
                        status, data2, text = await _request(
                            session,
                            "POST",
                            f"{settings.panel_url}/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
                        )
                        logger.info(
                            "DELETE VLESS [%s] STATUS: %s %s", inbound_id, status, text
                        )
                        if _ok(status, data2):
                            success = True
                    except Exception as e:
                        logger.error("DELETE VLESS [%s] ERROR: %s", inbound_id, e)

    return success


# ===== GET VPN DATA (subscription URL) =====

async def get_vpn_data(user_id: int) -> str | None:
    data = await get_inbounds()
    if not data:
        return None

    for inbound in data.get("obj", []):
        try:
            cfg = json.loads(inbound.get("settings", "{}"))
        except Exception:
            continue

        for client in cfg.get("clients", []):
            if client.get("email", "").startswith(str(user_id)):
                sub_id = client.get("subId")
                if sub_id:
                    return f"{settings.sub_base_url}/{sub_id}"

    return None


# ===== ONLINE USERS =====

async def get_online_users() -> list[str] | None:
    try:
        async with _new_session() as session:
            status, data, _ = await _request(
                session, "POST", f"{settings.panel_url}/panel/api/inbounds/onlines"
            )
            if status != 200:
                logger.error("ONLINE ERROR STATUS: %s", status)
                return None
            return (data or {}).get("obj") or []
    except Exception as e:
        logger.error("ONLINE ERROR: %s", e)
        return None

import requests
import json
import time
from uuid import uuid4

from config import (
    PANEL_URL,
    API_TOKEN,
    INBOUND_IDS,
    SUB_BASE_URL,
)

from database.db import get_username

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}


# ===== GET INBOUNDS =====
def get_inbounds():
    try:
        r = session.get(
            f"{PANEL_URL}/panel/api/inbounds/list",
            headers=HEADERS,
            verify=False
        )

        print("LIST STATUS:", r.status_code)
        print("LIST RAW:", r.text[:500])

        if r.status_code != 200:
            return None

        return r.json()

    except Exception as e:
        print("LIST ERROR:", e)
        return None


# ===== CREATE USER =====
def create_user(user_id, days):
    print("CREATE USER:", user_id)

    expire = int((time.time() + days * 86400) * 1000)

    username = get_username(user_id) or f"user_{user_id}"

    sub_id = str(uuid4()).replace("-", "")[:16]

    success = False

    for inbound_id in INBOUND_IDS:

        client_uuid = str(uuid4())

        client = {
            "id": client_uuid,
            "email": f"{user_id}_{inbound_id}",
            "enable": True,
            "expiryTime": expire,
            "limitIp": 1,
            "totalGB": 0,
            "subId": sub_id,
            "comment": username
        }

        payload = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [client]
            })
        }

        try:
            r = session.post(
                f"{PANEL_URL}/panel/api/inbounds/addClient",
                headers=HEADERS,
                json=payload,
                verify=False
            )

            print("ADD STATUS:", r.status_code)
            print("ADD RAW:", r.text)

            if r.status_code == 200:
                success = True

        except Exception as e:
            print("ADD ERROR:", e)

    return success


# ===== DELETE USER =====
def delete_user(user_id):
    print("DELETE USER:", user_id)

    data = get_inbounds()

    if not data:
        print("NO INBOUNDS")
        return False

    success = False

    for inbound in data.get("obj", []):

        inbound_id = inbound.get("id")

        # settings приходит строкой JSON
        settings_raw = inbound.get("settings", "{}")

        try:
            settings = json.loads(settings_raw)
        except Exception as e:
            print("SETTINGS JSON ERROR:", e)
            continue

        clients = settings.get("clients", [])

        for client in clients:

            email = client.get("email", "")
            client_id = client.get("id")

            print("CHECK:", email)

            if email.startswith(str(user_id)):

                print("FOUND:", email, client_id)

                try:
                    r = session.post(
                        f"{PANEL_URL}/panel/api/inbounds/{inbound_id}/delClient/{client_id}",
                        headers=HEADERS,
                        verify=False
                    )

                    print("DELETE STATUS:", r.status_code)
                    print("DELETE RAW:", r.text)

                    if r.status_code == 200:
                        success = True

                except Exception as e:
                    print("DELETE ERROR:", e)

    return success


# ===== GET SUB =====
def get_vpn_data(user_id):

    data = get_inbounds()

    if not data:
        return None

    for inbound in data.get("obj", []):

        for client in inbound.get("clientStats", []):

            email = client.get("email", "")

            if email.startswith(str(user_id)):

                sub_id = client.get("subId")

                if sub_id:
                    return f"{SUB_BASE_URL}/{sub_id}"

    return None
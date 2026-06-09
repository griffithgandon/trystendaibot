from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Позволяет использовать списки через запятую в .env
        # например: ADMIN_IDS=1,2,3
        extra="ignore",
    )

    # ===== Bot =====
    bot_token: str

    # ===== Admins =====
    admin_ids: list[int] = []
    admin_usernames: list[str] = []

    # ===== Database =====
    db_path: str = "bot.db"

    # ===== Redis =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== 3X-UI Panel =====
    panel_url: str
    api_token: str
    vless_inbound_ids: list[int] = []
    hysteria_inbound_id: int = 0
    hysteria_enabled: bool = False
    panel_verify: str = "true"  # "true" | "false" | "/path/to/cert"

    # ===== Subscription =====
    sub_base_url: str
    domain: str = ""

    # ===== Hysteria2 =====
    hysteria_api_url: str = ""
    hysteria_api_key: str = ""
    hysteria_host: str = ""
    hysteria_port: int = 443
    hysteria_sni: str = ""

    # ===== Payment =====
    sbp_number: str = ""
    card_number: str = ""

    # ===== Trial =====
    trial_days: int = 7
    trial_auto_approve: bool = False

    # ===== Servers =====
    server_1_name: str = "Сервер 1"
    server_1_url: str = ""
    server_2_name: str = "Сервер 2"
    server_2_url: str = ""

    # ===== Validators =====

    @field_validator("admin_ids", "vless_inbound_ids", mode="before")
    @classmethod
    def parse_int_list(cls, v: str | list) -> list[int]:
        """'1,2,3' → [1, 2, 3]"""
        if isinstance(v, list):
            return v
        return [int(x.strip()) for x in str(v).split(",") if x.strip().isdigit()]

    @field_validator("admin_usernames", mode="before")
    @classmethod
    def parse_str_list(cls, v: str | list) -> list[str]:
        """'user1,user2' → ['user1', 'user2']"""
        if isinstance(v, list):
            return v
        return [x.strip() for x in str(v).split(",") if x.strip()]

    @model_validator(mode="after")
    def validate_panel(self) -> "Settings":
        if not self.panel_url:
            raise ValueError("PANEL_URL не может быть пустым")
        if not self.api_token:
            raise ValueError("API_TOKEN не может быть пустым")
        if not self.sub_base_url:
            raise ValueError("SUB_BASE_URL не может быть пустым")
        return self

    # ===== Properties =====

    @property
    def ssl_verify(self) -> bool | str:
        """
        Возвращает то что ожидает aiohttp/requests:
        True | False | "/path/to/cert.crt"
        """
        v = self.panel_verify.lower()
        if v == "true":
            return True
        if v == "false":
            return False
        return self.panel_verify  # путь к CA-файлу

    @property
    def payment_text(self) -> str:
        admins = "\n".join(f"@{u}" for u in self.admin_usernames if u)
        return (
            "💳 Оплата VPN\n\n"
            "📌 После оплаты нажмите кнопку ниже\n\n"
            "Способы оплаты:\n\n"
            f"💸 СБП:\n{self.sbp_number}\n\n"
            f"💳 Карта:\n{self.card_number}\n\n"
            f"Перед оплатой напишите одному из админов 👉 {admins}\n\n"
            "📝 В комментарии укажите свой Telegram ID"
        )

    @property
    def servers(self) -> list[dict]:
        result = []
        for name, url in (
            (self.server_1_name, self.server_1_url),
            (self.server_2_name, self.server_2_url),
        ):
            if url:
                result.append({"name": name, "url": url})
        return result

    @property
    def tariffs(self) -> dict[str, dict]:
        return {
            "1": {"title": "30 дней — 150₽",  "days": 30,  "price": 150},
            "2": {"title": "90 дней — 450₽",  "days": 90,  "price": 450},
            "3": {"title": "180 дней — 900₽", "days": 180, "price": 900},
            "4": {"title": "360 дней — 1500₽","days": 360, "price": 1500},
        }


@lru_cache
def get_settings() -> Settings:
    """
    Синглтон — читает .env один раз при первом вызове.
    В тестах можно переопределить через get_settings.cache_clear().
    """
    return Settings()
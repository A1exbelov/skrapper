from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., alias="TELEGRAM_CHAT_ID")
    config_path: Path = Field(Path("config.yaml"), alias="CONFIG_PATH")
    database_path: Path = Field(Path("data/skrapper.sqlite3"), alias="DATABASE_PATH")
    check_interval_seconds: int = Field(300, alias="CHECK_INTERVAL_SECONDS")
    http_timeout_seconds: int = Field(20, alias="HTTP_TIMEOUT_SECONDS")
    user_agent: str = Field(
        "Mozilla/5.0 (compatible; SkrapperApartmentBot/0.1)",
        alias="USER_AGENT",
    )
    email_imap_host: str | None = Field(None, alias="EMAIL_IMAP_HOST")
    email_imap_port: int = Field(993, alias="EMAIL_IMAP_PORT")
    email_imap_username: str | None = Field(None, alias="EMAIL_IMAP_USERNAME")
    email_imap_password: str | None = Field(None, alias="EMAIL_IMAP_PASSWORD")
    email_imap_use_ssl: bool = Field(True, alias="EMAIL_IMAP_USE_SSL")

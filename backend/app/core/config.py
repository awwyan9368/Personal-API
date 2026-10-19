import os
import secrets
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = PROJECT_ROOT / "exports"
BACKUPS_DIR = PROJECT_ROOT / "backups"

for directory in (DATA_DIR, EXPORTS_DIR, BACKUPS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def _get_or_create_secret_key() -> str:
    env_key = os.getenv("SECRET_KEY")
    if env_key and env_key != "replace-with-secure-random-hex-secret-key-generated-on-setup":
        return env_key
    secret_file = DATA_DIR / ".secret_key"
    if secret_file.exists():
        stored = secret_file.read_text(encoding="utf-8").strip()
        if len(stored) >= 32:
            return stored
    generated = secrets.token_hex(32)
    try:
        secret_file.write_text(generated, encoding="utf-8")
    except OSError:
        pass
    return generated


class Settings(BaseSettings):
    APP_NAME: str = "Personal Life OS"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    SECRET_KEY: str = _get_or_create_secret_key()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    DATABASE_URL: str = f"sqlite:///{(DATA_DIR / 'personal_life_os.db').as_posix()}"

    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    ENABLE_EXTERNAL_INTEGRATIONS: bool = False

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


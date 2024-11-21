from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_channels: str  # Comma-separated list of channels
    telegram_api_id: str
    telegram_api_hash: str
    telegram_session: str
    mongodb_url: str
    database_name: str
    anthropic_api_key: str

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings():
    return Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 60 * 60 * 24 * 7

    tusd_hook_secret: str

    media_root: str = "/media"
    domain: str = "localhost"
    tz: str = "Europe/Kyiv"


settings = Settings()  # type: ignore[call-arg]

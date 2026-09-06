from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    brevo_api_key: str
    from_email: str
    notify_email: str
    gemini_api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
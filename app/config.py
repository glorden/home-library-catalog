from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Каталог домашней библиотеки"
    debug: bool = False
    database_url: str = "postgresql+psycopg://library:library@localhost:5432/library"
    photo_storage_root: str = "data/photos"
    settings_encryption_key: str | None = None
    enable_draft_cleanup_loop: bool = True
    session_secret_key: str | None = None
    showcase_public: bool = True
    ai_extraction_daily_limit: int = 30
    ai_proxy_url: str | None = None


settings = Settings()

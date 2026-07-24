from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Каталог домашней библиотеки"
    debug: bool = False
    database_url: str = "postgresql+psycopg://library:library@localhost:5432/library"
    photo_storage_root: str = "data/photos"


settings = Settings()

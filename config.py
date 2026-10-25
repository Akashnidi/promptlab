from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        APP_NAME: str = "PromptLab v1"
        MASTER_PASSWORD_HASH: Optional[str] = None
        DATA_DIR: str = "data"
        UPLOAD_DIR: str = "data/uploads"
        HISTORY_FILE: str = "data/history.json"
        VAULT_FILE: str = "data/.vault.json"

except ImportError:
    from pydantic import BaseSettings  # type: ignore

    class Settings(BaseSettings):  # type: ignore
        APP_NAME: str = "PromptLab v1"
        MASTER_PASSWORD_HASH: Optional[str] = None
        DATA_DIR: str = "data"
        UPLOAD_DIR: str = "data/uploads"
        HISTORY_FILE: str = "data/history.json"
        VAULT_FILE: str = "data/.vault.json"

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"


settings = Settings()

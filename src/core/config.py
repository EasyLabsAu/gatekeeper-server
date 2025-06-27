from pydantic import (
    computed_field,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Gatekeeper Server"
    VERSION: str = "0.1.0"

    # Environment settings
    BASE_URL: str = ""
    ENV: str = "development"

    # JWT settings
    JWT_SECRET: str = "secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # Email settings
    SMTP_SERVER: str = ""
    SMTP_PORT: int = 0
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_SENDER_EMAIL: str = ""

    # Logging settings
    LOG_DIR: str = "logs"
    LOG_FILE: str = "server.log"
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_FILE_BACKUP_COUNT: int = 5

    # Redis settings
    REDIS_HOST: str = ""
    REDIS_USER: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # CORS settings
    CORS_ORIGINS: str = "*"  # Comma-separated list of allowed origins

    # PostgreSQL settings
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "gatekeeper"
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10

    @computed_field
    @property
    def POSTGRES_URI(self) -> MultiHostUrl:
        if self.POSTGRES_USER != "" and self.POSTGRES_PASSWORD != "":
            return MultiHostUrl.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        else:
            return MultiHostUrl.build(
                scheme="postgresql+psycopg",
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

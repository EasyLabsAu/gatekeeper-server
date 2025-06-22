from pydantic import (
    computed_field,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Bootstrapped"
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
    POSTGRESQL_USER: str = ""
    POSTGRESQL_PASSWORD: str = ""
    POSTGRESQL_HOST: str = "localhost"
    POSTGRESQL_PORT: int = 5432
    POSTGRESQL_DB: str = "fastapi"
    POSTGRESQL_POOL_SIZE: int = 5
    POSTGRESQL_MAX_OVERFLOW: int = 10

    @computed_field
    @property
    def POSTGRES_URI(self) -> MultiHostUrl:
        if (
            self.ENV == "production"
            and self.POSTGRESQL_USER
            and self.POSTGRESQL_PASSWORD
        ):
            # Use full credentials for production
            return MultiHostUrl.build(
                scheme="postgresql+psycopg",
                username=self.POSTGRESQL_USER,
                password=self.POSTGRESQL_PASSWORD,
                host=self.POSTGRESQL_HOST,
                port=self.POSTGRESQL_PORT,
                path=self.POSTGRESQL_DB,
            )
        else:
            # In development, skip username/password and connect via local peer
            return MultiHostUrl.build(
                scheme="postgresql+psycopg",
                host=self.POSTGRESQL_HOST,
                port=self.POSTGRESQL_PORT,
                path=self.POSTGRESQL_DB,
            )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

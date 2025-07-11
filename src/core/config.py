from pydantic import computed_field, field_validator
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Gatekeeper Server"
    VERSION: str = "0.1.0"

    # LLM Settings
    LLM_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_PROVIDER: str = ""

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

    @computed_field
    @property
    def REDIS_URI(self) -> MultiHostUrl:
        if self.REDIS_USER != "" and self.REDIS_PASSWORD != "":
            return MultiHostUrl.build(
                scheme="redis",
                username=self.REDIS_USER,
                password=self.REDIS_PASSWORD,
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path=f"{self.REDIS_DB}",
            )
        else:
            return MultiHostUrl.build(
                scheme="redis",
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path=f"{self.REDIS_DB}",
            )

    # CORS settings
    CORS_ORIGINS: list[str] = []  # Comma-separated list of allowed origins

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str] | None) -> list[str]:
        if not value:
            return ["*"]
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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

    # Slack settings
    SLACK_INFO_WEBHOOK: str = ""
    SLACK_ERROR_WEBHOOK: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

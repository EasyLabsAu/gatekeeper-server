from src.core.config import settings

PROVIDER_CREATED_EVENT = "provider_created"
PROVIDER_DELETED_EVENT = "provider_deleted"
PROVIDER_UPDATED_EVENT = "provider_updated"
PROVIDER_VERIFIED_EVENT = "provider_verified"
PROVIDER_PASSWORD_RESET_EVENT = "provider_password_reset"
PROVIDER_ACCOUNT_RECOVERY_EVENT = "provider_account_recovery"

HTTP_API_PREFIX = "/api/rest"
WEBSOCKET_API_PREFIX = "/api/websocket"


CORS_CONFIGS: dict[str, bool | list[str] | str] = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

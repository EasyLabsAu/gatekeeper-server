from fastapi import APIRouter

from src.api.rest.consumers import consumer_router
from src.api.rest.forms import form_router
from src.api.rest.providers import provider_router
from src.api.rest.sessions import session_router
from src.api.websocket import chat  # noqa: F401


def setup_http_routes(prefix: str) -> APIRouter:
    """Configure and return the main API router with all routes."""
    router = APIRouter(prefix=prefix)
    router.include_router(provider_router)
    router.include_router(consumer_router)
    router.include_router(session_router)
    router.include_router(form_router)

    return router

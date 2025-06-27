from fastapi import APIRouter

from api.v1.consumers import consumer_router
from api.v1.forms import form_router
from api.v1.providers import provider_router
from api.v1.sessions import session_router


def setup_routes() -> APIRouter:
    """Configure and return the main API router with all routes."""
    router = APIRouter()
    router.include_router(provider_router)
    router.include_router(consumer_router)
    router.include_router(session_router)
    router.include_router(form_router)

    return router

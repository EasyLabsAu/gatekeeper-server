from fastapi import APIRouter

from api.v1.providers import provider_router


def setup_routes() -> APIRouter:
    """Configure and return the main API router with all routes."""
    router = APIRouter()
    router.include_router(provider_router)
    return router

from fastapi import APIRouter

from api.v1.users import user_router


def setup_routes() -> APIRouter:
    """Configure and return the main API router with all routes."""
    router = APIRouter()
    router.include_router(user_router)
    return router

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Depends

from helpers.auth import public_route, require_auth
from helpers.utils import APIResponse
from models.sessions import (
    SessionCreate,
    SessionQuery,
    SessionRead,
    SessionStatus,
    SessionUpdate,
)
from services.sessions import SessionService

session_router: APIRouter = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
session_service: SessionService = SessionService()


@session_router.post(
    "/", response_model=APIResponse[SessionRead], summary="Create a new session"
)
@public_route
async def create_session(payload: SessionCreate):
    return await session_service.create(payload)


@session_router.get(
    "/", response_model=APIResponse[SessionRead], summary="List sessions"
)
async def list_sessions(
    _: Annotated[dict[str, Any], Depends(require_auth)],
    status: SessionStatus | None = None,
    tags: list[str] | None = None,
    skip: int = 0,
    limit: int = 20,
):
    query = SessionQuery(status=status, tags=tags)
    return await session_service.find(query, skip=skip, limit=limit)


@session_router.get(
    "/{session_id}",
    response_model=APIResponse[SessionRead],
    summary="Get session by ID",
)
async def get_session(
    session_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await session_service.get(session_id)


@session_router.patch(
    "/{session_id}",
    response_model=APIResponse[SessionRead],
    summary="Update session by ID",
)
async def update_session(
    session_id: UUID,
    payload: SessionUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await session_service.update(session_id, payload)


@session_router.delete(
    "/{session_id}", response_model=APIResponse, summary="Soft delete session by ID"
)
async def delete_session(
    session_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await session_service.delete(session_id)

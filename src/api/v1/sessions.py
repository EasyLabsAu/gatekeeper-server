from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Depends

from helpers.auth import require_auth
from helpers.model import APIResponse
from models.sessions import (
    SessionCreate,
    SessionQuery,
    SessionRead,
    SessionStatus,
    SessionUpdate,
)
from repositories.sessions import SessionRepository

session_router: APIRouter = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])
session_repository: SessionRepository = SessionRepository()


@session_router.post(
    "/", response_model=APIResponse[SessionRead], summary="Create a new session"
)
async def create_session(payload: SessionCreate):
    return await session_repository.create(payload)


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
    return await session_repository.find(query, skip=skip, limit=limit)


@session_router.get(
    "/{session_id}",
    response_model=APIResponse[SessionRead],
    summary="Get session by ID",
)
async def get_session(
    session_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await session_repository.get(session_id)


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
    return await session_repository.update(session_id, payload)


@session_router.delete(
    "/{session_id}", response_model=APIResponse, summary="Soft delete session by ID"
)
async def delete_session(
    session_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await session_repository.delete(session_id)

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Depends

from src.helpers.auth import require_auth
from src.helpers.model import APIResponse
from src.models.contexts import (
    ContextCreate,
    ContextQuery,
    ContextRead,
    ContextUpdate,
)
from src.repositories.contexts import ContextRepository

context_router: APIRouter = APIRouter(prefix="/contexts", tags=["contexts"])
context_repository: ContextRepository = ContextRepository()


@context_router.post(
    "/", response_model=APIResponse[ContextRead], summary="Create a new context"
)
async def create_context(payload: ContextCreate):
    return await context_repository.create(payload)


@context_router.get(
    "/", response_model=APIResponse[ContextRead], summary="List contexts"
)
async def list_contexts(
    _: Annotated[dict[str, Any], Depends(require_auth)],
    name: str | None = None,
    skip: int = 0,
    limit: int = 20,
):
    query = ContextQuery(name=name)
    return await context_repository.find(query, skip=skip, limit=limit)


@context_router.get(
    "/{context_id}",
    response_model=APIResponse[ContextRead],
    summary="Get context by ID",
)
async def get_context(
    context_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await context_repository.get(context_id)


@context_router.patch(
    "/{context_id}",
    response_model=APIResponse[ContextRead],
    summary="Update context by ID",
)
async def update_context(
    context_id: UUID,
    payload: ContextUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await context_repository.update(context_id, payload)


@context_router.delete(
    "/{context_id}", response_model=APIResponse, summary="Soft delete context by ID"
)
async def delete_context(
    context_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await context_repository.delete(context_id)

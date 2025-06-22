from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from helpers.auth import public_route, require_auth
from helpers.utils import APIResponse
from models.consumers import (
    ConsumerCreate,
    ConsumerQuery,
    ConsumerRead,
    ConsumerUpdate,
)
from services.consumers import ConsumerService

consumer_router: APIRouter = APIRouter(prefix="/api/v1/consumers", tags=["consumers"])
consumer_service: ConsumerService = ConsumerService()


@consumer_router.post(
    "/", response_model=APIResponse[ConsumerRead], summary="Create a new consumer"
)
@public_route
async def create_consumer(payload: ConsumerCreate):
    return await consumer_service.create(payload)


@consumer_router.get(
    "/", response_model=APIResponse[ConsumerRead], summary="List consumers"
)
async def list_consumers(
    _: Annotated[dict[str, Any], Depends(require_auth)],
    query: ConsumerQuery = Depends(ConsumerQuery),
    skip: int = 0,
    limit: int = 20,
):
    return await consumer_service.find(query, skip=skip, limit=limit)


@consumer_router.get(
    "/{consumer_id}",
    response_model=APIResponse[ConsumerRead],
    summary="Get consumer by ID",
)
async def get_consumer(
    consumer_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await consumer_service.get(consumer_id)


@consumer_router.patch(
    "/{consumer_id}",
    response_model=APIResponse[ConsumerRead],
    summary="Update consumer by ID",
)
async def update_consumer(
    consumer_id: UUID,
    payload: ConsumerUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await consumer_service.update(consumer_id, payload)


@consumer_router.delete(
    "/{consumer_id}", response_model=APIResponse, summary="Soft delete consumer by ID"
)
async def delete_consumer(
    consumer_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await consumer_service.delete(consumer_id)

from typing import Annotated, Any

from fastapi import APIRouter
from fastapi.params import Depends

from src.helpers.auth import require_auth
from src.helpers.constants import PROVIDER_CREATED_EVENT
from src.helpers.events import events
from src.helpers.model import APIResponse
from src.models.providers import (
    ProviderAuthRead,
    ProviderCreate,
    ProviderInvalidate,
    ProviderManage,
    ProviderManageAction,
    ProviderManageRead,
    ProviderRead,
    ProviderRevalidate,
    ProviderUpdate,
    ProviderValidate,
)
from src.repositories.providers import ProviderRepository

provider_router: APIRouter = APIRouter(prefix="/api/v1/providers", tags=["providers"])
provider_repository: ProviderRepository = ProviderRepository()


@provider_router.get(
    "/account",
    response_model=APIResponse[ProviderRead],
    summary="Get current provider info",
)
async def get(auth: Annotated[dict[str, Any], Depends(require_auth)]):
    return await provider_repository.get(auth["sub"])


@provider_router.patch(
    "/account", response_model=APIResponse[ProviderRead], summary="Update provider info"
)
async def update(
    payload: ProviderUpdate, auth: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await provider_repository.update(auth["sub"], payload)


@provider_router.post(
    "/account",
    response_model=APIResponse[ProviderRead],
    summary="Create a new provider account",
)
async def create(payload: ProviderCreate):
    result = await provider_repository.create(payload)
    if result:
        await events.emit(PROVIDER_CREATED_EVENT, payload.email)
    return result


@provider_router.post(
    "/account/validate",
    response_model=APIResponse[ProviderAuthRead],
    summary="Validate provider credentials",
)
async def validate(payload: ProviderValidate):
    return await provider_repository.validate(payload)


@provider_router.post(
    "/account/revalidate",
    response_model=APIResponse[ProviderAuthRead],
    summary="Revalidate a session",
)
async def revalidate(payload: ProviderRevalidate):
    return await provider_repository.revalidate(payload)


@provider_router.post(
    "/account/invalidate",
    response_model=ProviderManageRead,
    summary="Invalidate a session",
)
async def invalidate(payload: ProviderInvalidate):
    return await provider_repository.invalidate(payload)


@provider_router.post(
    "/account/manage/start-email-verification", response_model=ProviderManageRead
)
async def manage_start_email_verification(payload: ProviderManage):
    return await provider_repository.manage(
        ProviderManageAction.START_EMAIL_VERIFICATION, payload
    )


@provider_router.post(
    "/account/manage/finish-email-verification", response_model=ProviderManageRead
)
async def manage_finish_email_verification(payload: ProviderManage):
    return await provider_repository.manage(
        ProviderManageAction.FINISH_EMAIL_VERIFICATION, payload
    )


@provider_router.post(
    "/account/manage/start-email-authentication", response_model=ProviderManageRead
)
async def manage_start_email_authentication(payload: ProviderManage):
    return await provider_repository.manage(
        ProviderManageAction.START_EMAIL_AUTHENTICATION, payload
    )


@provider_router.post(
    "/account/manage/finish-email-authentication", response_model=ProviderManageRead
)
async def manage_finish_email_authentication(payload: ProviderManage):
    return await provider_repository.manage(
        ProviderManageAction.FINISH_EMAIL_AUTHENTICATION, payload
    )


@provider_router.post(
    "/account/manage/start-password-reset", response_model=ProviderManageRead
)
async def manage_start_password_reset(payload: ProviderManage):
    return await provider_repository.manage(
        ProviderManageAction.START_PASSWORD_RESET, payload
    )


@provider_router.post(
    "/account/manage/finish-password-reset", response_model=ProviderManageRead
)
async def manage_finish_password_reset(payload: ProviderManage):
    return await provider_repository.manage(
        ProviderManageAction.FINISH_PASSWORD_RESET, payload
    )


@provider_router.post("/account/manage/update-email", response_model=ProviderManageRead)
async def manage_update_email(
    payload: ProviderManage,
):
    return await provider_repository.manage(ProviderManageAction.UPDATE_EMAIL, payload)


@provider_router.post(
    "/account/manage/update-password", response_model=ProviderManageRead
)
async def manage_update_password(
    payload: ProviderManage,
):
    return await provider_repository.manage(
        ProviderManageAction.UPDATE_PASSWORD, payload
    )

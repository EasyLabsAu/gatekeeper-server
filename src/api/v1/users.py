from typing import Annotated, Any

from fastapi import APIRouter
from fastapi.params import Depends

from helpers.auth import public_route, require_auth
from helpers.constants import USER_CREATED_EVENT
from helpers.events import events
from helpers.utils import APIResponse
from models.users import (
    UserAuthRead,
    UserCreate,
    UserInvalidate,
    UserManage,
    UserManageAction,
    UserManageRead,
    UserRead,
    UserRevalidate,
    UserUpdate,
    UserValidate,
)
from services.users import UserService

user_router: APIRouter = APIRouter(prefix="/api/v1/users", tags=["users"])
user_service: UserService = UserService()


@user_router.get(
    "/account", response_model=APIResponse[UserRead], summary="Get current user info"
)
async def get(auth: Annotated[dict[str, Any], Depends(require_auth)]):
    return await user_service.get(auth["sub"])


@user_router.patch(
    "/account", response_model=APIResponse[UserRead], summary="Update user info"
)
async def update(
    payload: UserUpdate, auth: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await user_service.update(auth["sub"], payload)


@user_router.post(
    "/account",
    response_model=APIResponse[UserRead],
    summary="Create a new user account",
)
@public_route
async def create(payload: UserCreate):
    result = await user_service.create(payload)
    if result:
        await events.emit(USER_CREATED_EVENT, payload.email)
    return result


@user_router.post(
    "/account/validate",
    response_model=APIResponse[UserAuthRead],
    summary="Validate user credentials",
)
@public_route
async def validate(payload: UserValidate):
    return await user_service.validate(payload)


@user_router.post(
    "/account/revalidate",
    response_model=APIResponse[UserAuthRead],
    summary="Revalidate a session",
)
async def revalidate(payload: UserRevalidate):
    return await user_service.revalidate(payload)


@user_router.post(
    "/account/invalidate", response_model=UserManageRead, summary="Invalidate a session"
)
async def invalidate(payload: UserInvalidate):
    return await user_service.invalidate(payload)


@user_router.post(
    "/account/manage/start-email-verification", response_model=UserManageRead
)
@public_route
async def manage_start_email_verification(payload: UserManage):
    return await user_service.manage(UserManageAction.START_EMAIL_VERIFICATION, payload)


@user_router.post(
    "/account/manage/finish-email-verification", response_model=UserManageRead
)
@public_route
async def manage_finish_email_verification(payload: UserManage):
    return await user_service.manage(
        UserManageAction.FINISH_EMAIL_VERIFICATION, payload
    )


@user_router.post(
    "/account/manage/start-email-authentication", response_model=UserManageRead
)
@public_route
async def manage_start_email_authentication(payload: UserManage):
    return await user_service.manage(
        UserManageAction.START_EMAIL_AUTHENTICATION, payload
    )


@user_router.post(
    "/account/manage/finish-email-authentication", response_model=UserManageRead
)
@public_route
async def manage_finish_email_authentication(payload: UserManage):
    return await user_service.manage(
        UserManageAction.FINISH_EMAIL_AUTHENTICATION, payload
    )


@user_router.post("/account/manage/start-password-reset", response_model=UserManageRead)
@public_route
async def manage_start_password_reset(payload: UserManage):
    return await user_service.manage(UserManageAction.START_PASSWORD_RESET, payload)


@user_router.post(
    "/account/manage/finish-password-reset", response_model=UserManageRead
)
@public_route
async def manage_finish_password_reset(payload: UserManage):
    return await user_service.manage(UserManageAction.FINISH_PASSWORD_RESET, payload)


@user_router.post("/account/manage/update-email", response_model=UserManageRead)
async def manage_update_email(
    payload: UserManage,
):
    return await user_service.manage(UserManageAction.UPDATE_EMAIL, payload)


@user_router.post("/account/manage/update-password", response_model=UserManageRead)
async def manage_update_password(
    payload: UserManage,
):
    return await user_service.manage(UserManageAction.UPDATE_PASSWORD, payload)

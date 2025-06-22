from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from helpers.auth import (
    create_access_token,
    create_one_time_password,
    create_refresh_token,
    hash_password,
    rotate_refresh_token,
    token_blacklist,
    verify_password,
    verify_refresh_token,
)
from helpers.repository import BaseRepository
from helpers.utils import APIError, APIResponse
from models.users import (
    UserAuthRead,
    UserCreate,
    UserInvalidate,
    UserManage,
    UserManageAction,
    UserQuery,
    UserRead,
    UserRevalidate,
    Users,
    UserUpdate,
    UserValidate,
)


class UserService(BaseRepository):
    async def create(self, payload: UserCreate) -> APIResponse[UserRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Users).where(
                Users.email == payload.email,
                Users.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(statement)
            if result.scalar_one_or_none():
                raise APIError(409, "User with this email already exists")

            user = Users(
                **payload.model_dump(exclude={"password"}),
                password=hash_password(payload.password),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            data = UserRead.model_validate(user).model_dump()
            return APIResponse[UserRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self,
        query: UserQuery,
        skip: int = 0,
        limit: int = 20,
        exclude_deleted: bool = True,
    ) -> APIResponse[UserRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            if query.first_name:
                filters.append(Users.first_name == query.first_name)
            if query.last_name:
                filters.append(Users.last_name == query.last_name)
            if query.email:
                filters.append(Users.email == query.email)
            if exclude_deleted:
                filters.append(Users.is_deleted == False)  # noqa: E712

            statement = select(Users)
            if filters:
                statement = statement.where(*filters)

            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            users = result.scalars().all()

            data = [UserRead.model_validate(user) for user in users]
            return APIResponse[UserRead](
                data=[item.model_dump() for item in data],
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(
        self, id: UUID, include_deleted: bool = False
    ) -> APIResponse[UserRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Users).where(Users.id == id)
            if not include_deleted:
                statement = statement.where(Users.is_deleted == False)  # noqa: E712

            result = await db.execute(statement)
            user = result.scalar_one_or_none()

            if not user:
                raise APIError(404, "User not found")

            data = UserRead.model_validate(user).model_dump()
            return APIResponse[UserRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: UserUpdate
    ) -> APIResponse[UserRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Users).where(Users.id == id, Users.is_deleted == False)  # noqa: E712
            result = await db.execute(statement)
            user = result.scalar_one_or_none()

            if not user:
                raise APIError(404, "User not found")

            update_data = payload.model_dump(exclude_unset=True)

            new_email = update_data.get("email")
            if new_email and new_email != user.email:
                email_check_statement = select(Users).where(
                    Users.email == new_email,
                    Users.id != id,
                    Users.is_deleted == False,  # noqa: E712
                )
                email_check = await db.execute(email_check_statement)
                if email_check.scalar_one_or_none():
                    raise APIError(409, "Another user with this email already exists")

            if "password" in update_data:
                update_data["password"] = hash_password(update_data["password"])

            for key, value in update_data.items():
                setattr(user, key, value)

            db.add(user)
            await db.commit()
            await db.refresh(user)
            data = UserRead.model_validate(user).model_dump()
            return APIResponse[UserRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Users).where(Users.id == id, Users.is_deleted == False)  # noqa: E712
            result = await db.execute(statement)
            user = result.scalar_one_or_none()

            if not user:
                raise APIError(404, "User not found")

            Users(user).soft_delete()
            db.add(user)
            await db.commit()
            return APIResponse(message="User soft-deleted")
        finally:
            await self.close_database_session()

    async def validate(self, payload: UserValidate) -> APIResponse[UserAuthRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            stmt = select(Users).where(
                Users.email == payload.email,
                Users.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise APIError(404, "User not found")

            if not verify_password(payload.password, user.password):
                raise APIError(401, "Invalid credentials")

            user.authenticated_at = datetime.utcnow()
            db.add(user)
            await db.commit()
            await db.refresh(user)

            data = {
                "auth": {
                    "access_token": create_access_token(user.id),
                    "refresh_token": create_refresh_token(user.id),
                },
                "user": UserRead.model_validate(user).model_dump(),
            }
            return APIResponse[UserAuthRead](data=data)
        finally:
            await self.close_database_session()

    async def revalidate(
        self, payload: UserRevalidate
    ) -> APIResponse[UserAuthRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            auth_data = verify_refresh_token(payload.refresh_token)
            if not auth_data:
                raise APIError(401, "Invalid or expired refresh token")

            user_email = auth_data["sub"]
            access_token, new_refresh_token = rotate_refresh_token(
                payload.refresh_token
            )

            stmt = select(Users).where(
                Users.email == user_email,
                Users.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise APIError(404, "User not found")

            data = {
                "auth": {
                    "access_token": access_token,
                    "refresh_token": new_refresh_token,
                },
                "user": UserRead.model_validate(user).model_dump(),
            }
            return APIResponse[UserAuthRead](data=data)
        finally:
            await self.close_database_session()

    async def invalidate(self, payload: UserInvalidate) -> APIResponse | None:
        auth_data = verify_refresh_token(payload.refresh_token)
        if not auth_data:
            raise APIError(401, "Invalid or expired refresh token")

        jti = auth_data.get("jti")
        if jti:
            token_blacklist.add(jti)

        return APIResponse(message="Successfully logged out")

    async def manage(
        self, action: UserManageAction, payload: UserManage
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            stmt = select(Users).where(
                Users.email == payload.email,
                Users.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            user_or_none = result.scalar_one_or_none()
            if not user_or_none:
                raise APIError(404, "User not found")

            user = cast(Users, user_or_none)

            action_handlers: dict[str, Callable[[], Awaitable[APIResponse | None]]] = {
                "start-email-verification": lambda: self.handle_start_email_verification(
                    payload.email, user, db
                ),
                "finish-email-verification": lambda: self.handle_finish_email_verification(
                    payload, payload.email, user, db
                ),
                "start-email-authentication": lambda: self.handle_start_email_authentication(
                    payload.email, user, db
                ),
                "finish-email-authentication": lambda: self.handle_finish_email_authentication(
                    payload, payload.email, user, db
                ),
                "start-password-reset": lambda: self.handle_start_password_reset(
                    payload.email, user, db
                ),
                "finish-password-reset": lambda: self.handle_finish_password_reset(
                    payload, payload.email, user, db
                ),
                "update-email": lambda: self.handle_update_email(
                    payload, payload.email, user, db
                ),
                "update-password": lambda: self.handle_update_password(
                    payload, payload.email, user, db
                ),
            }

            handler = action_handlers.get(action)
            if not handler:
                raise APIError(400, f"Error: Action - {action} is invalid.")

            return await handler()

        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database error while managing user") from e
        finally:
            await self.close_database_session()

    async def handle_start_email_verification(
        self, email: str, user: Users, db: AsyncSession
    ):
        if user.is_verified:
            return APIResponse(message="User is already verified")
        else:
            user.verification_token = create_one_time_password()
            user.verification_token_expires = datetime.now(timezone.utc) + timedelta(
                minutes=60 * 24
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return APIResponse(message="Verification token sent")

    async def handle_finish_email_verification(
        self,
        payload: UserManage,
        email: str,
        user: Users,
        db: AsyncSession,
    ):
        if payload.token != user.verification_token:
            raise APIError(400, "Invalid verification token")
        if (
            not user.verification_token_expires
            or datetime.now(timezone.utc) > user.verification_token_expires
        ):
            raise APIError(400, "Verification token expired")

        user.verification_token = None
        user.verification_token_expires = None
        user.is_verified = True
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Email successfully verified")

    async def handle_start_email_authentication(
        self, email: str, user: Users, db: AsyncSession
    ):
        user.authentication_token = create_one_time_password()
        user.authentication_token_expires = datetime.now(timezone.utc) + timedelta(
            minutes=5
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Authentication token sent")

    async def handle_finish_email_authentication(
        self,
        payload: UserManage,
        email: str,
        user: Users,
        db: AsyncSession,
    ):
        if payload.token != user.authentication_token:
            raise APIError(400, "Invalid authentication token")
        if (
            not user.authentication_token_expires
            or datetime.now(timezone.utc) > user.authentication_token_expires
        ):
            raise APIError(400, "Authentication token expired")

        user.authentication_token = None
        user.authentication_token_expires = None
        user.authenticated_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Authentication successful")

    async def handle_start_password_reset(
        self, email: str, user: Users, db: AsyncSession
    ):
        user.reset_token = create_one_time_password()
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=60)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Password reset token sent")

    async def handle_finish_password_reset(
        self,
        payload: UserManage,
        email: str,
        user: Users,
        db: AsyncSession,
    ):
        if payload.token != user.reset_token:
            raise APIError(400, "Invalid reset token")
        if (
            not user.reset_token_expires
            or datetime.now(timezone.utc) > user.reset_token_expires
        ):
            raise APIError(400, "Reset token expired")
        if not payload.new_password:
            raise APIError(400, "Missing new password")

        user.password = hash_password(payload.new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Password has been reset successfully")

    async def handle_update_email(
        self,
        payload: UserManage,
        email: str,
        user: Users,
        db: AsyncSession,
    ):
        if not payload.new_email:
            raise APIError(400, "Missing new email")
        if payload.new_email == email:
            raise APIError(400, "New email cannot be the same as current email")
        user.email = payload.new_email
        user.is_verified = False
        user.verification_token = create_one_time_password()
        user.verification_token_expires = datetime.now(timezone.utc) + timedelta(
            minutes=60 * 24
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Email updated and verification required")

    async def handle_update_password(
        self,
        payload: UserManage,
        email: str,
        user: Users,
        db: AsyncSession,
    ):
        if not payload.new_password:
            raise APIError(400, "Missing new password")
        if not payload.password or not verify_password(payload.password, user.password):
            raise APIError(401, "Invalid current password")
        user.password = hash_password(payload.new_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return APIResponse(message="Password updated successfully")

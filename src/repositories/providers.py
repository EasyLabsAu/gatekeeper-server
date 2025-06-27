from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.helpers.auth import (
    create_access_token,
    create_one_time_password,
    create_refresh_token,
    hash_password,
    rotate_refresh_token,
    token_blacklist,
    verify_password,
    verify_refresh_token,
)
from src.helpers.model import APIError, APIResponse
from src.helpers.repository import BaseRepository
from src.models.providers import (
    ProviderAuthRead,
    ProviderAuthTokens,
    ProviderCreate,
    ProviderInvalidate,
    ProviderManage,
    ProviderManageAction,
    ProviderQuery,
    ProviderRead,
    ProviderRevalidate,
    Providers,
    ProviderUpdate,
    ProviderValidate,
)


class ProviderRepository(BaseRepository):
    async def create(self, payload: ProviderCreate) -> APIResponse[ProviderRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Providers).where(
                Providers.email == payload.email,
                Providers.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(statement)
            if result.scalar_one_or_none():
                raise APIError(409, "Provider with this email already exists")

            provider = Providers(
                **payload.model_dump(exclude={"password"}),
                password=hash_password(payload.password),
            )
            db.add(provider)
            await db.commit()
            await db.refresh(provider)
            data = ProviderRead.model_validate(provider)
            return APIResponse[ProviderRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self,
        query: ProviderQuery,
        skip: int = 0,
        limit: int = 20,
        exclude_deleted: bool = True,
    ) -> APIResponse[list[ProviderRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            if query.first_name:
                filters.append(Providers.first_name == query.first_name)
            if query.last_name:
                filters.append(Providers.last_name == query.last_name)
            if query.email:
                filters.append(Providers.email == query.email)
            if exclude_deleted:
                filters.append(Providers.is_deleted == False)  # noqa: E712

            statement = select(Providers)
            if filters:
                statement = statement.where(*filters)

            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            providers = result.scalars().all()

            data = [ProviderRead.model_validate(provider) for provider in providers]
            return APIResponse[list[ProviderRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(
        self, id: UUID, include_deleted: bool = False
    ) -> APIResponse[ProviderRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Providers).where(Providers.id == id)
            if not include_deleted:
                statement = statement.where(Providers.is_deleted == False)  # noqa: E712

            result = await db.execute(statement)
            provider = result.scalar_one_or_none()

            if not provider:
                raise APIError(404, "Provider not found")

            data = ProviderRead.model_validate(provider)
            return APIResponse[ProviderRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: ProviderUpdate
    ) -> APIResponse[ProviderRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Providers).where(
                Providers.id == id,
                Providers.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(statement)
            provider = result.scalar_one_or_none()

            if not provider:
                raise APIError(404, "Provider not found")

            update_data = payload.model_dump(exclude_unset=True)

            new_email = update_data.get("email")
            if new_email and new_email != provider.email:
                email_check_statement = select(Providers).where(
                    Providers.email == new_email,
                    Providers.id != id,
                    Providers.is_deleted == False,  # noqa: E712
                )
                email_check = await db.execute(email_check_statement)
                if email_check.scalar_one_or_none():
                    raise APIError(
                        409, "Another provider with this email already exists"
                    )

            if "password" in update_data:
                update_data["password"] = hash_password(update_data["password"])

            for key, value in update_data.items():
                setattr(provider, key, value)

            db.add(provider)
            await db.commit()
            await db.refresh(provider)
            data = ProviderRead.model_validate(provider)
            return APIResponse[ProviderRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Providers).where(
                Providers.id == id,
                Providers.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(statement)
            provider = result.scalar_one_or_none()

            if not provider:
                raise APIError(404, "Provider not found")

            provider.soft_delete()
            db.add(provider)
            await db.commit()
            return APIResponse(message="Provider soft-deleted")
        finally:
            await self.close_database_session()

    async def validate(
        self, payload: ProviderValidate
    ) -> APIResponse[ProviderAuthRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            stmt = select(Providers).where(
                Providers.email == payload.email,
                Providers.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            provider = result.scalar_one_or_none()

            if not provider:
                raise APIError(404, "Provider not found")

            if not verify_password(payload.password, provider.password):
                raise APIError(401, "Invalid credentials")

            provider.authenticated_at = datetime.utcnow()
            db.add(provider)
            await db.commit()
            await db.refresh(provider)

            data = ProviderAuthRead(
                auth=ProviderAuthTokens(
                    access_token=create_access_token(provider.id),
                    refresh_token=create_refresh_token(provider.id),
                ),
                provider=ProviderRead.model_validate(provider),
            )
            return APIResponse[ProviderAuthRead](data=data)
        finally:
            await self.close_database_session()

    async def revalidate(
        self, payload: ProviderRevalidate
    ) -> APIResponse[ProviderAuthRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            auth_data = verify_refresh_token(payload.refresh_token)
            if not auth_data:
                raise APIError(401, "Invalid or expired refresh token")

            provider_email = auth_data["sub"]
            access_token, new_refresh_token = rotate_refresh_token(
                payload.refresh_token
            )

            stmt = select(Providers).where(
                Providers.email == provider_email,
                Providers.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            provider = result.scalar_one_or_none()

            if not provider:
                raise APIError(404, "Provider not found")

            data = ProviderAuthRead(
                auth=ProviderAuthTokens(
                    access_token=access_token,
                    refresh_token=new_refresh_token,
                ),
                provider=ProviderRead.model_validate(provider),
            )
            return APIResponse[ProviderAuthRead](data=data)
        finally:
            await self.close_database_session()

    async def invalidate(self, payload: ProviderInvalidate) -> APIResponse | None:
        auth_data = verify_refresh_token(payload.refresh_token)
        if not auth_data:
            raise APIError(401, "Invalid or expired refresh token")

        jti = auth_data.get("jti")
        if jti:
            token_blacklist.add(jti)

        return APIResponse(message="Successfully logged out")

    async def manage(
        self, action: ProviderManageAction, payload: ProviderManage
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            print(payload)
            stmt = select(Providers).where(
                Providers.email == payload.email,
                Providers.is_deleted == False,  # noqa: E712
            )
            result = await db.execute(stmt)
            provider_or_none = result.scalar_one_or_none()

            print(provider_or_none)

            if not provider_or_none:
                raise APIError(404, "Provider not found")

            provider = cast(Providers, provider_or_none)

            action_handlers: dict[str, Callable[[], Awaitable[APIResponse | None]]] = {
                "start-email-verification": lambda: self.handle_start_email_verification(
                    payload.email, provider, db
                ),
                "finish-email-verification": lambda: self.handle_finish_email_verification(
                    payload, payload.email, provider, db
                ),
                "start-email-authentication": lambda: self.handle_start_email_authentication(
                    payload.email, provider, db
                ),
                "finish-email-authentication": lambda: self.handle_finish_email_authentication(
                    payload, payload.email, provider, db
                ),
                "start-password-reset": lambda: self.handle_start_password_reset(
                    payload.email, provider, db
                ),
                "finish-password-reset": lambda: self.handle_finish_password_reset(
                    payload, payload.email, provider, db
                ),
                "update-email": lambda: self.handle_update_email(
                    payload, payload.email, provider, db
                ),
                "update-password": lambda: self.handle_update_password(
                    payload, payload.email, provider, db
                ),
            }

            handler = action_handlers.get(action)
            if not handler:
                raise APIError(400, f"Error: Action - {action} is invalid.")

            return await handler()

        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database error while managing provider") from e
        finally:
            await self.close_database_session()

    async def handle_start_email_verification(
        self, email: str, provider: Providers, db: AsyncSession
    ):
        if provider.is_verified:
            return APIResponse(message="Provider is already verified")
        else:
            provider.verification_token = create_one_time_password()
            provider.verification_token_expires = datetime.now(
                timezone.utc
            ) + timedelta(minutes=60 * 24)
            db.add(provider)
            await db.commit()
            await db.refresh(provider)
            return APIResponse(message="Verification token sent")

    async def handle_finish_email_verification(
        self,
        payload: ProviderManage,
        email: str,
        provider: Providers,
        db: AsyncSession,
    ):
        if payload.token != provider.verification_token:
            raise APIError(400, "Invalid verification token")
        if (
            not provider.verification_token_expires
            or datetime.now(timezone.utc) > provider.verification_token_expires
        ):
            raise APIError(400, "Verification token expired")

        provider.verification_token = None
        provider.verification_token_expires = None
        provider.is_verified = True
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Email successfully verified")

    async def handle_start_email_authentication(
        self, email: str, provider: Providers, db: AsyncSession
    ):
        provider.authentication_token = create_one_time_password()
        provider.authentication_token_expires = datetime.now(timezone.utc) + timedelta(
            minutes=5
        )
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Authentication token sent")

    async def handle_finish_email_authentication(
        self,
        payload: ProviderManage,
        email: str,
        provider: Providers,
        db: AsyncSession,
    ):
        if payload.token != provider.authentication_token:
            raise APIError(400, "Invalid authentication token")
        if (
            not provider.authentication_token_expires
            or datetime.now(timezone.utc) > provider.authentication_token_expires
        ):
            raise APIError(400, "Authentication token expired")

        provider.authentication_token = None
        provider.authentication_token_expires = None
        provider.authenticated_at = datetime.now(timezone.utc)
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Authentication successful")

    async def handle_start_password_reset(
        self, email: str, provider: Providers, db: AsyncSession
    ):
        provider.reset_token = create_one_time_password()
        provider.reset_token_expires = datetime.now(timezone.utc) + timedelta(
            minutes=60
        )
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Password reset token sent")

    async def handle_finish_password_reset(
        self,
        payload: ProviderManage,
        email: str,
        provider: Providers,
        db: AsyncSession,
    ):
        if payload.token != provider.reset_token:
            raise APIError(400, "Invalid reset token")
        if (
            not provider.reset_token_expires
            or datetime.now(timezone.utc) > provider.reset_token_expires
        ):
            raise APIError(400, "Reset token expired")
        if not payload.new_password:
            raise APIError(400, "Missing new password")

        provider.password = hash_password(payload.new_password)
        provider.reset_token = None
        provider.reset_token_expires = None
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Password has been reset successfully")

    async def handle_update_email(
        self,
        payload: ProviderManage,
        email: str,
        provider: Providers,
        db: AsyncSession,
    ):
        if not payload.new_email:
            raise APIError(400, "Missing new email")
        if payload.new_email == email:
            raise APIError(400, "New email cannot be the same as current email")
        provider.email = payload.new_email
        provider.is_verified = False
        provider.verification_token = create_one_time_password()
        provider.verification_token_expires = datetime.now(timezone.utc) + timedelta(
            minutes=60 * 24
        )
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Email updated and verification required")

    async def handle_update_password(
        self,
        payload: ProviderManage,
        email: str,
        provider: Providers,
        db: AsyncSession,
    ):
        if not payload.new_password:
            raise APIError(400, "Missing new password")
        if not payload.password or not verify_password(
            payload.password, provider.password
        ):
            raise APIError(401, "Invalid current password")
        provider.password = hash_password(payload.new_password)
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        return APIResponse(message="Password updated successfully")

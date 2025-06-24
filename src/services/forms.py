from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from helpers.repository import BaseRepository
from helpers.utils import APIError, APIResponse
from models.forms import (
    FormCreate,
    FormQuery,
    FormQuestionResponses,
    FormQuestions,
    FormRead,
    FormResponses,
    Forms,
    FormSectionResponses,
    FormSections,
    FormUpdate,
)


class FormService(BaseRepository):
    async def create(self, payload: FormCreate) -> APIResponse[FormRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            form = Forms(**payload.model_dump())
            db.add(form)
            await db.commit()
            await db.refresh(form)
            data = FormRead.model_validate(form)
            return APIResponse[FormRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self,
        query: FormQuery,
        skip: int = 0,
        limit: int = 20,
        exclude_deleted: bool = True,
    ) -> APIResponse[list[FormRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            if query.name:
                filters.append(getattr(Forms, "name") == query.name)  # noqa: B009
            if query.created_by:
                filters.append(getattr(Forms, "created_by") == query.created_by)  # noqa: B009
            if query.type:
                filters.append(getattr(Forms, "type") == query.type)  # noqa: B009
            if exclude_deleted and hasattr(Forms, "is_deleted"):
                filters.append(getattr(Forms, "is_deleted") == False)  # noqa: B009, E712
            statement = select(Forms)
            if filters:
                statement = statement.where(*filters)
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            forms = result.scalars().all()
            data = [FormRead.model_validate(form) for form in forms]
            return APIResponse[list[FormRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(
        self, id: UUID, include_deleted: bool = False
    ) -> APIResponse[FormRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Forms).where(Forms.id == id)
            if not include_deleted and hasattr(Forms, "is_deleted"):
                statement = statement.where(getattr(Forms, "is_deleted") == False)  # noqa: B009, E712
            result = await db.execute(statement)
            form = result.scalar_one_or_none()
            if not form:
                raise APIError(404, "Form not found")
            data = FormRead.model_validate(form)
            return APIResponse[FormRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: FormUpdate
    ) -> APIResponse[FormRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Forms).where(
                Forms.id == id,
                (getattr(Forms, "is_deleted") == False)  # noqa: B009, E712
                if hasattr(Forms, "is_deleted")
                else True,
            )
            result = await db.execute(statement)
            form = result.scalar_one_or_none()
            if not form:
                raise APIError(404, "Form not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(form, key, value)
            db.add(form)
            await db.commit()
            await db.refresh(form)
            data = FormRead.model_validate(form)
            return APIResponse[FormRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(Forms).where(
                Forms.id == id,
                (getattr(Forms, "is_deleted") == False)  # noqa: B009, E712
                if hasattr(Forms, "is_deleted")
                else True,
            )
            result = await db.execute(statement)
            form = result.scalar_one_or_none()
            if not form:
                raise APIError(404, "Form not found")
            if hasattr(form, "soft_delete"):
                form.soft_delete()
            elif hasattr(form, "is_deleted"):
                form.is_deleted = True
            else:
                raise APIError(400, "Soft delete not supported on Forms model")
            db.add(form)
            await db.commit()
            return APIResponse(message="Form soft-deleted")
        finally:
            await self.close_database_session()


class FormSectionService(BaseRepository):
    async def create(self, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            section = FormSections(**payload)
            db.add(section)
            await db.commit()
            await db.refresh(section)
            return APIResponse(data=section)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, form_id: UUID, skip: int = 0, limit: int = 20
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSections).where(FormSections.form_id == form_id)
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            sections = result.scalars().all()
            return APIResponse(data=list(sections))
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSections).where(FormSections.id == id)
            result = await db.execute(statement)
            section = result.scalar_one_or_none()
            if not section:
                raise APIError(404, "Form section not found")
            return APIResponse(data=section)
        finally:
            await self.close_database_session()

    async def update(self, id: UUID, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSections).where(FormSections.id == id)
            result = await db.execute(statement)
            section = result.scalar_one_or_none()
            if not section:
                raise APIError(404, "Form section not found")
            for key, value in payload.items():
                setattr(section, key, value)
            db.add(section)
            await db.commit()
            await db.refresh(section)
            return APIResponse(data=section)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSections).where(FormSections.id == id)
            result = await db.execute(statement)
            section = result.scalar_one_or_none()
            if not section:
                raise APIError(404, "Form section not found")
            if hasattr(section, "soft_delete"):
                section.soft_delete()
            elif hasattr(section, "is_deleted"):
                section.is_deleted = True
            else:
                raise APIError(400, "Soft delete not supported on FormSections model")
            db.add(section)
            await db.commit()
            return APIResponse(message="Form section soft-deleted")
        finally:
            await self.close_database_session()


class FormQuestionService(BaseRepository):
    async def create(self, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            question = FormQuestions(**payload)
            db.add(question)
            await db.commit()
            await db.refresh(question)
            return APIResponse(data=question)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, section_id: UUID, skip: int = 0, limit: int = 20
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(
                FormQuestions.section_id == section_id
            )
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            questions = result.scalars().all()
            return APIResponse(data=list(questions))
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(FormQuestions.id == id)
            result = await db.execute(statement)
            question = result.scalar_one_or_none()
            if not question:
                raise APIError(404, "Form question not found")
            return APIResponse(data=question)
        finally:
            await self.close_database_session()

    async def update(self, id: UUID, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(FormQuestions.id == id)
            result = await db.execute(statement)
            question = result.scalar_one_or_none()
            if not question:
                raise APIError(404, "Form question not found")
            for key, value in payload.items():
                setattr(question, key, value)
            db.add(question)
            await db.commit()
            await db.refresh(question)
            return APIResponse(data=question)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(FormQuestions.id == id)
            result = await db.execute(statement)
            question = result.scalar_one_or_none()
            if not question:
                raise APIError(404, "Form question not found")
            if hasattr(question, "soft_delete"):
                question.soft_delete()
            elif hasattr(question, "is_deleted"):
                question.is_deleted = True
            else:
                raise APIError(400, "Soft delete not supported on FormQuestions model")
            db.add(question)
            await db.commit()
            return APIResponse(message="Form question soft-deleted")
        finally:
            await self.close_database_session()


class FormResponseService(BaseRepository):
    async def create(self, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            response = FormResponses(**payload)
            db.add(response)
            await db.commit()
            await db.refresh(response)
            return APIResponse(data=response)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, form_id: UUID, skip: int = 0, limit: int = 20
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormResponses).where(FormResponses.form_id == form_id)
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            responses = result.scalars().all()
            return APIResponse(data=list(responses))
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormResponses).where(FormResponses.id == id)
            result = await db.execute(statement)
            response = result.scalar_one_or_none()
            if not response:
                raise APIError(404, "Form response not found")
            return APIResponse(data=response)
        finally:
            await self.close_database_session()

    async def update(self, id: UUID, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormResponses).where(FormResponses.id == id)
            result = await db.execute(statement)
            response = result.scalar_one_or_none()
            if not response:
                raise APIError(404, "Form response not found")
            for key, value in payload.items():
                setattr(response, key, value)
            db.add(response)
            await db.commit()
            await db.refresh(response)
            return APIResponse(data=response)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormResponses).where(FormResponses.id == id)
            result = await db.execute(statement)
            response = result.scalar_one_or_none()
            if not response:
                raise APIError(404, "Form response not found")
            if hasattr(response, "soft_delete"):
                response.soft_delete()
            elif hasattr(response, "is_deleted"):
                response.is_deleted = True
            else:
                raise APIError(400, "Soft delete not supported on FormResponses model")
            db.add(response)
            await db.commit()
            return APIResponse(message="Form response soft-deleted")
        finally:
            await self.close_database_session()


class FormSectionResponseService(BaseRepository):
    async def create(self, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            section_response = FormSectionResponses(**payload)
            db.add(section_response)
            await db.commit()
            await db.refresh(section_response)
            return APIResponse(data=section_response)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, response_id: UUID, skip: int = 0, limit: int = 20
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSectionResponses).where(
                FormSectionResponses.response_id == response_id
            )
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            section_responses = result.scalars().all()
            return APIResponse(data=list(section_responses))
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSectionResponses).where(
                FormSectionResponses.id == id
            )
            result = await db.execute(statement)
            section_response = result.scalar_one_or_none()
            if not section_response:
                raise APIError(404, "Form section response not found")
            return APIResponse(data=section_response)
        finally:
            await self.close_database_session()

    async def update(self, id: UUID, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSectionResponses).where(
                FormSectionResponses.id == id
            )
            result = await db.execute(statement)
            section_response = result.scalar_one_or_none()
            if not section_response:
                raise APIError(404, "Form section response not found")
            for key, value in payload.items():
                setattr(section_response, key, value)
            db.add(section_response)
            await db.commit()
            await db.refresh(section_response)
            return APIResponse(data=section_response)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSectionResponses).where(
                FormSectionResponses.id == id
            )
            result = await db.execute(statement)
            section_response = result.scalar_one_or_none()
            if not section_response:
                raise APIError(404, "Form section response not found")
            if hasattr(section_response, "soft_delete"):
                section_response.soft_delete()
            elif hasattr(section_response, "is_deleted"):
                section_response.is_deleted = True
            else:
                raise APIError(
                    400, "Soft delete not supported on FormSectionResponses model"
                )
            db.add(section_response)
            await db.commit()
            return APIResponse(message="Form section response soft-deleted")
        finally:
            await self.close_database_session()


class FormQuestionResponseService(BaseRepository):
    async def create(self, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            question_response = FormQuestionResponses(**payload)
            db.add(question_response)
            await db.commit()
            await db.refresh(question_response)
            return APIResponse(data=question_response)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, section_response_id: UUID, skip: int = 0, limit: int = 20
    ) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.section_response_id == section_response_id
            )
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            question_responses = result.scalars().all()
            return APIResponse(data=list(question_responses))
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.id == id
            )
            result = await db.execute(statement)
            question_response = result.scalar_one_or_none()
            if not question_response:
                raise APIError(404, "Form question response not found")
            return APIResponse(data=question_response)
        finally:
            await self.close_database_session()

    async def update(self, id: UUID, payload: dict) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.id == id
            )
            result = await db.execute(statement)
            question_response = result.scalar_one_or_none()
            if not question_response:
                raise APIError(404, "Form question response not found")
            for key, value in payload.items():
                setattr(question_response, key, value)
            db.add(question_response)
            await db.commit()
            await db.refresh(question_response)
            return APIResponse(data=question_response)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def delete(self, id: UUID) -> APIResponse | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.id == id
            )
            result = await db.execute(statement)
            question_response = result.scalar_one_or_none()
            if not question_response:
                raise APIError(404, "Form question response not found")
            if hasattr(question_response, "soft_delete"):
                question_response.soft_delete()
            elif hasattr(question_response, "is_deleted"):
                question_response.is_deleted = True
            else:
                raise APIError(
                    400, "Soft delete not supported on FormQuestionResponses model"
                )
            db.add(question_response)
            await db.commit()
            return APIResponse(message="Form question response soft-deleted")
        finally:
            await self.close_database_session()

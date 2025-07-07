from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.helpers.model import APIError, APIResponse
from src.helpers.repository import BaseRepository
from src.models.forms import (
    FormCreate,
    FormQuery,
    FormQuestionResponses,
    FormQuestionResponsesCreate,
    FormQuestionResponsesQuery,
    FormQuestionResponsesRead,
    FormQuestionResponsesUpdate,
    FormQuestions,
    FormQuestionsCreate,
    FormQuestionsQuery,
    FormQuestionsRead,
    FormQuestionsUpdate,
    FormRead,
    FormResponses,
    FormResponsesCreate,
    FormResponsesQuery,
    FormResponsesRead,
    FormResponsesUpdate,
    Forms,
    FormSectionResponses,
    FormSectionResponsesCreate,
    FormSectionResponsesQuery,
    FormSectionResponsesRead,
    FormSectionResponsesUpdate,
    FormSections,
    FormSectionsCreate,
    FormSectionsQuery,
    FormSectionsRead,
    FormSectionsUpdate,
    FormUpdate,
)


class FormRepository(BaseRepository):
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
                filters.append(Forms.name == query.name)
            if query.created_by:
                filters.append(Forms.created_by == query.created_by)
            if query.type:
                filters.append(Forms.type == query.type)
            if exclude_deleted and hasattr(Forms, "is_deleted"):
                filters.append(Forms.is_deleted == False)

            statement = (
                select(Forms)
                .options(
                    selectinload(getattr(Forms, "sections")).selectinload(
                        getattr(FormSections, "questions")
                    )
                )
                .offset(skip)
                .limit(limit)
            )

            if filters:
                statement = statement.where(*filters)

            result = await db.execute(statement)
            forms = result.scalars().unique().all()
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
            statement = (
                select(Forms)
                .where(Forms.id == id)
                .options(
                    selectinload(getattr(Forms, "sections")).selectinload(
                        getattr(FormSections, "questions")
                    )
                )
            )
            if not include_deleted and hasattr(Forms, "is_deleted"):
                statement = statement.where(Forms.is_deleted == False)

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


class FormSectionRepository(BaseRepository):
    async def create(
        self, payload: FormSectionsCreate
    ) -> APIResponse[FormSectionsRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            section = FormSections(**payload.model_dump())
            db.add(section)
            await db.commit()
            await db.refresh(section)
            data = FormSectionsRead.model_validate(section)
            return APIResponse[FormSectionsRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, query: FormSectionsQuery, skip: int = 0, limit: int = 20
    ) -> APIResponse[list[FormSectionsRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = (
                select(FormSections)
                .where(FormSections.form_id == query.form_id)
                .options(selectinload(getattr(FormSections, "questions")))
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(statement)
            sections = result.scalars().unique().all()
            data = [FormSectionsRead.model_validate(section) for section in sections]
            return APIResponse[list[FormSectionsRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse[FormSectionsRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = (
                select(FormSections)
                .where(FormSections.id == id)
                .options(selectinload(getattr(FormSections, "questions")))
            )
            result = await db.execute(statement)
            section = result.scalar_one_or_none()
            if not section:
                raise APIError(404, "Form section not found")
            data = FormSectionsRead.model_validate(section)
            return APIResponse[FormSectionsRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: FormSectionsUpdate
    ) -> APIResponse[FormSectionsRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSections).where(FormSections.id == id)
            result = await db.execute(statement)
            section = result.scalar_one_or_none()
            if not section:
                raise APIError(404, "Form section not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(section, key, value)
            db.add(section)
            await db.commit()
            await db.refresh(section)
            data = FormSectionsRead.model_validate(section)
            return APIResponse[FormSectionsRead](data=data)
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


class FormQuestionRepository(BaseRepository):
    async def create(
        self, payload: FormQuestionsCreate
    ) -> APIResponse[FormQuestionsRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            question = FormQuestions(**payload.model_dump())
            db.add(question)
            await db.commit()
            await db.refresh(question)
            data = FormQuestionsRead.model_validate(question)
            return APIResponse[FormQuestionsRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, query: FormQuestionsQuery, skip: int = 0, limit: int = 20
    ) -> APIResponse[list[FormQuestionsRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(
                FormQuestions.section_id == query.section_id
            )
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            questions = result.scalars().all()
            data = [
                FormQuestionsRead.model_validate(question) for question in questions
            ]
            return APIResponse[list[FormQuestionsRead]](data=data)
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse[FormQuestionsRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(FormQuestions.id == id)
            result = await db.execute(statement)
            question = result.scalar_one_or_none()
            if not question:
                raise APIError(404, "Form question not found")
            data = FormQuestionsRead.model_validate(question)
            return APIResponse[FormQuestionsRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: FormQuestionsUpdate
    ) -> APIResponse[FormQuestionsRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestions).where(FormQuestions.id == id)
            result = await db.execute(statement)
            question = result.scalar_one_or_none()
            if not question:
                raise APIError(404, "Form question not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(question, key, value)
            db.add(question)
            await db.commit()
            await db.refresh(question)
            data = FormQuestionsRead.model_validate(question)
            return APIResponse[FormQuestionsRead](data=data)
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


class FormResponseRepository(BaseRepository):
    async def create(
        self, payload: FormResponsesCreate
    ) -> APIResponse[FormResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            response = FormResponses(**payload.model_dump())
            db.add(response)
            await db.commit()
            await db.refresh(response)
            data = FormResponsesRead.model_validate(response)
            return APIResponse[FormResponsesRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, query: FormResponsesQuery, skip: int = 0, limit: int = 20
    ) -> APIResponse[list[FormResponsesRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            filters = []
            if query.form_id:
                filters.append(FormResponses.form_id == query.form_id)
            if query.session_id:
                filters.append(FormResponses.session_id == query.session_id)

            statement = (
                select(FormResponses)
                .options(
                    selectinload(
                        getattr(FormResponses, "section_responses")
                    ).selectinload(getattr(FormSectionResponses, "question_responses"))
                )
                .offset(skip)
                .limit(limit)
            )

            if filters:
                statement = statement.where(*filters)

            result = await db.execute(statement)
            responses = result.scalars().unique().all()
            data = [
                FormResponsesRead.model_validate(response) for response in responses
            ]
            return APIResponse[list[FormResponsesRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse[FormResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormResponses).where(FormResponses.id == id)
            result = await db.execute(statement)
            response = result.scalar_one_or_none()
            if not response:
                raise APIError(404, "Form response not found")
            data = FormResponsesRead.model_validate(response)
            return APIResponse[FormResponsesRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: FormResponsesUpdate
    ) -> APIResponse[FormResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormResponses).where(FormResponses.id == id)
            result = await db.execute(statement)
            response = result.scalar_one_or_none()
            if not response:
                raise APIError(404, "Form response not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(response, key, value)
            db.add(response)
            await db.commit()
            await db.refresh(response)
            data = FormResponsesRead.model_validate(response)
            return APIResponse[FormResponsesRead](data=data)
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


class FormSectionResponseRepository(BaseRepository):
    async def create(
        self, payload: FormSectionResponsesCreate
    ) -> APIResponse[FormSectionResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            section_response = FormSectionResponses(**payload.model_dump())
            db.add(section_response)
            await db.commit()
            await db.refresh(section_response)
            data = FormSectionResponsesRead.model_validate(section_response)
            return APIResponse[FormSectionResponsesRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, query: FormSectionResponsesQuery, skip: int = 0, limit: int = 20
    ) -> APIResponse[list[FormSectionResponsesRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = (
                select(FormSectionResponses)
                .where(FormSectionResponses.response_id == query.response_id)
                .options(selectinload(getattr(FormSectionResponses, "question_responses")))
                .offset(skip)
                .limit(limit)
            )
            result = await db.execute(statement)
            section_responses = result.scalars().unique().all()
            data = [
                FormSectionResponsesRead.model_validate(sr) for sr in section_responses
            ]
            return APIResponse[list[FormSectionResponsesRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse[FormSectionResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSectionResponses).where(
                FormSectionResponses.id == id
            )
            result = await db.execute(statement)
            section_response = result.scalar_one_or_none()
            if not section_response:
                raise APIError(404, "Form section response not found")
            data = FormSectionResponsesRead.model_validate(section_response)
            return APIResponse[FormSectionResponsesRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: FormSectionResponsesUpdate
    ) -> APIResponse[FormSectionResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormSectionResponses).where(
                FormSectionResponses.id == id
            )
            result = await db.execute(statement)
            section_response = result.scalar_one_or_none()
            if not section_response:
                raise APIError(404, "Form section response not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(section_response, key, value)
            db.add(section_response)
            await db.commit()
            await db.refresh(section_response)
            data = FormSectionResponsesRead.model_validate(section_response)
            return APIResponse[FormSectionResponsesRead](data=data)
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


class FormQuestionResponseRepository(BaseRepository):
    async def create(
        self, payload: FormQuestionResponsesCreate
    ) -> APIResponse[FormQuestionResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            question_response = FormQuestionResponses(**payload.model_dump())
            db.add(question_response)
            await db.commit()
            await db.refresh(question_response)
            data = FormQuestionResponsesRead.model_validate(question_response)
            return APIResponse[FormQuestionResponsesRead](data=data)
        except IntegrityError as e:
            await db.rollback()
            raise APIError(400, "Database integrity error") from e
        finally:
            await self.close_database_session()

    async def find(
        self, query: FormQuestionResponsesQuery, skip: int = 0, limit: int = 20
    ) -> APIResponse[list[FormQuestionResponsesRead]] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.section_response_id == query.section_response_id
            )
            statement = statement.offset(skip).limit(limit)
            result = await db.execute(statement)
            question_responses = result.scalars().all()
            data = [
                FormQuestionResponsesRead.model_validate(qr)
                for qr in question_responses
            ]
            return APIResponse[list[FormQuestionResponsesRead]](
                data=data,
                meta={"skip": skip, "limit": limit, "count": len(data)},
            )
        finally:
            await self.close_database_session()

    async def get(self, id: UUID) -> APIResponse[FormQuestionResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.id == id
            )
            result = await db.execute(statement)
            question_response = result.scalar_one_or_none()
            if not question_response:
                raise APIError(404, "Form question response not found")
            data = FormQuestionResponsesRead.model_validate(question_response)
            return APIResponse[FormQuestionResponsesRead](data=data)
        finally:
            await self.close_database_session()

    async def update(
        self, id: UUID, payload: FormQuestionResponsesUpdate
    ) -> APIResponse[FormQuestionResponsesRead] | None:
        db: AsyncSession = await self.get_database_session()
        try:
            statement = select(FormQuestionResponses).where(
                FormQuestionResponses.id == id
            )
            result = await db.execute(statement)
            question_response = result.scalar_one_or_none()
            if not question_response:
                raise APIError(404, "Form question response not found")
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(question_response, key, value)
            db.add(question_response)
            await db.commit()
            await db.refresh(question_response)
            data = FormQuestionResponsesRead.model_validate(question_response)
            return APIResponse[FormQuestionResponsesRead](data=data)
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

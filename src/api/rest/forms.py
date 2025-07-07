from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Depends

from src.helpers.auth import require_auth
from src.helpers.model import APIResponse
from src.models.forms import (
    FormCreate,
    FormQuery,
    FormQuestionResponsesCreate,
    FormQuestionResponsesQuery,
    FormQuestionResponsesRead,
    FormQuestionResponsesUpdate,
    FormQuestionsCreate,
    FormQuestionsQuery,
    FormQuestionsRead,
    FormQuestionsUpdate,
    FormRead,
    FormResponsesCreate,
    FormResponsesQuery,
    FormResponsesRead,
    FormResponsesUpdate,
    FormSectionResponsesCreate,
    FormSectionResponsesQuery,
    FormSectionResponsesRead,
    FormSectionResponsesUpdate,
    FormSectionsCreate,
    FormSectionsQuery,
    FormSectionsRead,
    FormSectionsUpdate,
    FormUpdate,
)
from src.repositories.forms import (
    FormQuestionRepository,
    FormQuestionResponseRepository,
    FormRepository,
    FormResponseRepository,
    FormSectionRepository,
    FormSectionResponseRepository,
)

form_router: APIRouter = APIRouter(prefix="/forms", tags=["forms"])
form_repository: FormRepository = FormRepository()
section_repository: FormSectionRepository = FormSectionRepository()
question_repository: FormQuestionRepository = FormQuestionRepository()
response_repository: FormResponseRepository = FormResponseRepository()
section_response_repository: FormSectionResponseRepository = (
    FormSectionResponseRepository()
)
question_response_repository: FormQuestionResponseRepository = (
    FormQuestionResponseRepository()
)


@form_router.post(
    "/", response_model=APIResponse[FormRead], summary="Create a new form"
)
async def create_form(
    payload: FormCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await form_repository.create(payload)


@form_router.get("/", response_model=APIResponse[list[FormRead]], summary="List forms")
async def list_forms(
    name: str | None = None,
    created_by: UUID | None = None,
    type: str | None = None,
    skip: int = 0,
    limit: int = 20,
):
    query = FormQuery(name=name, created_by=created_by, type=type)
    return await form_repository.find(query, skip=skip, limit=limit)


@form_router.get(
    "/{form_id}",
    response_model=APIResponse[FormRead],
    summary="Get form by ID",
)
async def get_form(form_id: UUID):
    return await form_repository.get(form_id)


@form_router.patch(
    "/{form_id}",
    response_model=APIResponse[FormRead],
    summary="Update form by ID",
)
async def update_form(
    form_id: UUID,
    payload: FormUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await form_repository.update(form_id, payload)


@form_router.delete(
    "/{form_id}", response_model=APIResponse, summary="Soft delete form by ID"
)
async def delete_form(
    form_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await form_repository.delete(form_id)


@form_router.post(
    "/sections",
    response_model=APIResponse[FormSectionsRead],
    summary="Create section for a form",
)
async def create_section(
    payload: FormSectionsCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await section_repository.create(payload)


@form_router.get(
    "/sections",
    response_model=APIResponse[list[FormSectionsRead]],
    summary="List sections for a form",
)
async def list_sections(
    _: Annotated[dict[str, Any], Depends(require_auth)],
    form_id: UUID,
    skip: int = 0,
    limit: int = 20,
):
    return await section_repository.find(
        query=FormSectionsQuery(form_id=form_id), skip=skip, limit=limit
    )


@form_router.get(
    "/sections/{section_id}",
    response_model=APIResponse[FormSectionsRead],
    summary="Get section by ID",
)
async def get_section(
    section_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_repository.get(section_id)


@form_router.patch(
    "/sections/{section_id}",
    response_model=APIResponse[FormSectionsRead],
    summary="Update section by ID",
)
async def update_section(
    section_id: UUID,
    payload: FormSectionsUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await section_repository.update(section_id, payload)


@form_router.delete(
    "/sections/{section_id}", response_model=APIResponse, summary="Delete section by ID"
)
async def delete_section(
    section_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_repository.delete(section_id)


@form_router.post(
    "/sections/questions",
    response_model=APIResponse[FormQuestionsRead],
    summary="Create question for a section",
)
async def create_question(
    payload: FormQuestionsCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await question_repository.create(payload)


@form_router.get(
    "/sections/{section_id}/questions",
    response_model=APIResponse[list[FormQuestionsRead]],
    summary="List questions for a section",
)
async def list_questions(
    section_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await question_repository.find(
        query=FormQuestionsQuery(section_id=section_id), skip=skip, limit=limit
    )


@form_router.get(
    "/questions/{question_id}",
    response_model=APIResponse[FormQuestionsRead],
    summary="Get question by ID",
)
async def get_question(
    question_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_repository.get(question_id)


@form_router.patch(
    "/questions/{question_id}",
    response_model=APIResponse[FormQuestionsRead],
    summary="Update question by ID",
)
async def update_question(
    question_id: UUID,
    payload: FormQuestionsUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await question_repository.update(question_id, payload)


@form_router.delete(
    "/questions/{question_id}",
    response_model=APIResponse,
    summary="Delete question by ID",
)
async def delete_question(
    question_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_repository.delete(question_id)


@form_router.post(
    "/responses",
    response_model=APIResponse[FormResponsesRead],
    summary="Create response for a form",
)
async def create_response(
    payload: FormResponsesCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await response_repository.create(payload)


@form_router.get(
    "/{form_id}/responses",
    response_model=APIResponse[list[FormResponsesRead]],
    summary="List responses for a form",
)
async def list_responses(
    form_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    session_id: UUID | None = None,
    skip: int = 0,
    limit: int = 20,
):
    query = FormResponsesQuery(form_id=form_id, session_id=session_id)
    return await response_repository.find(
        query=query,
        skip=skip,
        limit=limit,
    )


@form_router.get(
    "/responses/{response_id}",
    response_model=APIResponse[FormResponsesRead],
    summary="Get response by ID",
)
async def get_response(
    response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await response_repository.get(response_id)


@form_router.patch(
    "/responses/{response_id}",
    response_model=APIResponse[FormResponsesRead],
    summary="Update response by ID",
)
async def update_response(
    response_id: UUID,
    payload: FormResponsesUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await response_repository.update(response_id, payload)


@form_router.delete(
    "/responses/{response_id}",
    response_model=APIResponse,
    summary="Delete response by ID",
)
async def delete_response(
    response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await response_repository.delete(response_id)


@form_router.post(
    "/responses/section-responses",
    response_model=APIResponse[FormSectionResponsesRead],
    summary="Create section response for a response",
)
async def create_section_response(
    payload: FormSectionResponsesCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await section_response_repository.create(payload)


@form_router.get(
    "/responses/{response_id}/section-responses",
    response_model=APIResponse[list[FormSectionResponsesRead]],
    summary="List section responses for a response",
)
async def list_section_responses(
    response_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await section_response_repository.find(
        query=FormSectionResponsesQuery(response_id=response_id),
        skip=skip,
        limit=limit,
    )


@form_router.get(
    "/section-responses/{section_response_id}",
    response_model=APIResponse[FormSectionResponsesRead],
    summary="Get section response by ID",
)
async def get_section_response(
    section_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_response_repository.get(section_response_id)


@form_router.patch(
    "/section-responses/{section_response_id}",
    response_model=APIResponse[FormSectionResponsesRead],
    summary="Update section response by ID",
)
async def update_section_response(
    section_response_id: UUID,
    payload: FormSectionResponsesUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await section_response_repository.update(section_response_id, payload)


@form_router.delete(
    "/section-responses/{section_response_id}",
    response_model=APIResponse,
    summary="Delete section response by ID",
)
async def delete_section_response(
    section_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_response_repository.delete(section_response_id)


@form_router.post(
    "/section-responses/question-responses",
    response_model=APIResponse[FormQuestionResponsesRead],
    summary="Create question response for a section response",
)
async def create_question_response(
    payload: FormQuestionResponsesCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await question_response_repository.create(payload)


@form_router.get(
    "/section-responses/{section_response_id}/question-responses",
    response_model=APIResponse[list[FormQuestionResponsesRead]],
    summary="List question responses for a section response",
)
async def list_question_responses(
    section_response_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await question_response_repository.find(
        query=FormQuestionResponsesQuery(section_response_id=section_response_id),
        skip=skip,
        limit=limit,
    )


@form_router.get(
    "/question-responses/{question_response_id}",
    response_model=APIResponse[FormQuestionResponsesRead],
    summary="Get question response by ID",
)
async def get_question_response(
    question_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_response_repository.get(question_response_id)


@form_router.patch(
    "/question-responses/{question_response_id}",
    response_model=APIResponse[FormQuestionResponsesRead],
    summary="Update question response by ID",
)
async def update_question_response(
    question_response_id: UUID,
    payload: FormQuestionResponsesUpdate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    return await question_response_repository.update(question_response_id, payload)


@form_router.delete(
    "/question-responses/{question_response_id}",
    response_model=APIResponse,
    summary="Delete question response by ID",
)
async def delete_question_response(
    question_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_response_repository.delete(question_response_id)

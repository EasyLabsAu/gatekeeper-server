from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Depends

from helpers.auth import require_auth
from helpers.model import APIResponse
from models.forms import (
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
from repositories.forms import (
    FormQuestionRepository,
    FormQuestionResponseRepository,
    FormRepository,
    FormResponseRepository,
    FormSectionRepository,
    FormSectionResponseRepository,
)

form_router: APIRouter = APIRouter(prefix="/api/v1/forms", tags=["forms"])
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
    _: Annotated[dict[str, Any], Depends(require_auth)],
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
async def get_form(form_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]):
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
    "/{form_id}/sections",
    response_model=APIResponse,
    summary="Create section for a form",
)
async def create_section(
    form_id: UUID,
    payload: FormSectionsCreate,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    payload_dict = payload.model_dump()
    payload_dict["form_id"] = str(form_id)
    payload_obj = FormSectionsCreate(**payload_dict)
    return await section_repository.create(payload_obj)


@form_router.get(
    "/{form_id}/sections",
    response_model=APIResponse,
    summary="List sections for a form",
)
async def list_sections(
    form_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await section_repository.find(
        query=FormSectionsQuery(form_id=form_id), skip=skip, limit=limit
    )


@form_router.get(
    "/sections/{section_id}", response_model=APIResponse, summary="Get section by ID"
)
async def get_section(
    section_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_repository.get(section_id)


@form_router.patch(
    "/sections/{section_id}", response_model=APIResponse, summary="Update section by ID"
)
async def update_section(
    section_id: UUID, payload: dict, _: Annotated[dict[str, Any], Depends(require_auth)]
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
    "/sections/{section_id}/questions",
    response_model=APIResponse,
    summary="Create question for a section",
)
async def create_question(
    section_id: UUID, payload: dict, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    payload["section_id"] = str(section_id)
    return await question_repository.create(payload)


@form_router.get(
    "/sections/{section_id}/questions",
    response_model=APIResponse,
    summary="List questions for a section",
)
async def list_questions(
    section_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await question_repository.find(section_id, skip=skip, limit=limit)


@form_router.get(
    "/questions/{question_id}", response_model=APIResponse, summary="Get question by ID"
)
async def get_question(
    question_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_repository.get(question_id)


@form_router.patch(
    "/questions/{question_id}",
    response_model=APIResponse,
    summary="Update question by ID",
)
async def update_question(
    question_id: UUID,
    payload: dict,
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
    "/{form_id}/responses",
    response_model=APIResponse,
    summary="Create response for a form",
)
async def create_response(
    form_id: UUID, payload: dict, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    payload["form_id"] = str(form_id)
    return await response_repository.create(payload)


@form_router.get(
    "/{form_id}/responses",
    response_model=APIResponse,
    summary="List responses for a form",
)
async def list_responses(
    form_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await response_repository.find(form_id, skip=skip, limit=limit)


@form_router.get(
    "/responses/{response_id}", response_model=APIResponse, summary="Get response by ID"
)
async def get_response(
    response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await response_repository.get(response_id)


@form_router.patch(
    "/responses/{response_id}",
    response_model=APIResponse,
    summary="Update response by ID",
)
async def update_response(
    response_id: UUID,
    payload: dict,
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
    "/responses/{response_id}/section-responses",
    response_model=APIResponse,
    summary="Create section response for a response",
)
async def create_section_response(
    response_id: UUID,
    payload: dict,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    payload["response_id"] = str(response_id)
    return await section_response_repository.create(payload)


@form_router.get(
    "/responses/{response_id}/section-responses",
    response_model=APIResponse,
    summary="List section responses for a response",
)
async def list_section_responses(
    response_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await section_response_repository.find(response_id, skip=skip, limit=limit)


@form_router.get(
    "/section-responses/{section_response_id}",
    response_model=APIResponse,
    summary="Get section response by ID",
)
async def get_section_response(
    section_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_response_repository.get(section_response_id)


@form_router.patch(
    "/section-responses/{section_response_id}",
    response_model=APIResponse,
    summary="Update section response by ID",
)
async def update_section_response(
    section_response_id: UUID,
    payload: dict,
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
    "/section-responses/{section_response_id}/question-responses",
    response_model=APIResponse,
    summary="Create question response for a section response",
)
async def create_question_response(
    section_response_id: UUID,
    payload: dict,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    payload["section_response_id"] = str(section_response_id)
    return await question_response_repository.create(payload)


@form_router.get(
    "/section-responses/{section_response_id}/question-responses",
    response_model=APIResponse,
    summary="List question responses for a section response",
)
async def list_question_responses(
    section_response_id: UUID,
    _: Annotated[dict[str, Any], Depends(require_auth)],
    skip: int = 0,
    limit: int = 20,
):
    return await question_response_repository.find(
        section_response_id, skip=skip, limit=limit
    )


@form_router.get(
    "/question-responses/{question_response_id}",
    response_model=APIResponse,
    summary="Get question response by ID",
)
async def get_question_response(
    question_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_response_repository.get(question_response_id)


@form_router.patch(
    "/question-responses/{question_response_id}",
    response_model=APIResponse,
    summary="Update question response by ID",
)
async def update_question_response(
    question_response_id: UUID,
    payload: dict,
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

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter
from fastapi.params import Depends

from helpers.auth import public_route, require_auth
from helpers.utils import APIResponse
from models.forms import (
    FormCreate,
    FormQuery,
    FormRead,
    FormUpdate,
)
from services.forms import (
    FormQuestionResponseService,
    FormQuestionService,
    FormResponseService,
    FormSectionResponseService,
    FormSectionService,
    FormService,
)

form_router: APIRouter = APIRouter(prefix="/api/v1/forms", tags=["forms"])
form_service: FormService = FormService()
section_service: FormSectionService = FormSectionService()
question_service: FormQuestionService = FormQuestionService()
response_service: FormResponseService = FormResponseService()
section_response_service: FormSectionResponseService = FormSectionResponseService()
question_response_service: FormQuestionResponseService = FormQuestionResponseService()


# --- Forms CRUD ---
@form_router.post(
    "/", response_model=APIResponse[FormRead], summary="Create a new form"
)
@public_route
async def create_form(payload: FormCreate):
    return await form_service.create(payload)


@form_router.get("/", response_model=APIResponse[list[FormRead]], summary="List forms")
async def list_forms(
    _: Annotated[dict[str, Any], Depends(require_auth)],
    name: str | None = None,
    description: str | None = None,
    created_by: UUID | None = None,
    type: str | None = None,
    skip: int = 0,
    limit: int = 20,
):
    query = FormQuery(
        name=name, description=description, created_by=created_by, type=type
    )
    return await form_service.find(query, skip=skip, limit=limit)


@form_router.get(
    "/{form_id}",
    response_model=APIResponse[FormRead],
    summary="Get form by ID",
)
async def get_form(form_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]):
    return await form_service.get(form_id)


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
    return await form_service.update(form_id, payload)


@form_router.delete(
    "/{form_id}", response_model=APIResponse, summary="Soft delete form by ID"
)
async def delete_form(
    form_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await form_service.delete(form_id)


# --- Form Sections CRUD ---
@form_router.post(
    "/{form_id}/sections",
    response_model=APIResponse,
    summary="Create section for a form",
)
async def create_section(
    form_id: UUID,
    payload: dict,
    _: Annotated[dict[str, Any], Depends(require_auth)],
):
    payload["form_id"] = str(form_id)
    return await section_service.create(payload)


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
    return await section_service.find(form_id, skip=skip, limit=limit)


@form_router.get(
    "/sections/{section_id}", response_model=APIResponse, summary="Get section by ID"
)
async def get_section(
    section_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_service.get(section_id)


@form_router.patch(
    "/sections/{section_id}", response_model=APIResponse, summary="Update section by ID"
)
async def update_section(
    section_id: UUID, payload: dict, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_service.update(section_id, payload)


@form_router.delete(
    "/sections/{section_id}", response_model=APIResponse, summary="Delete section by ID"
)
async def delete_section(
    section_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_service.delete(section_id)


# --- Form Questions CRUD ---
@form_router.post(
    "/sections/{section_id}/questions",
    response_model=APIResponse,
    summary="Create question for a section",
)
async def create_question(
    section_id: UUID, payload: dict, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    payload["section_id"] = str(section_id)
    return await question_service.create(payload)


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
    return await question_service.find(section_id, skip=skip, limit=limit)


@form_router.get(
    "/questions/{question_id}", response_model=APIResponse, summary="Get question by ID"
)
async def get_question(
    question_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_service.get(question_id)


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
    return await question_service.update(question_id, payload)


@form_router.delete(
    "/questions/{question_id}",
    response_model=APIResponse,
    summary="Delete question by ID",
)
async def delete_question(
    question_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_service.delete(question_id)


# --- Form Responses CRUD ---
@form_router.post(
    "/{form_id}/responses",
    response_model=APIResponse,
    summary="Create response for a form",
)
async def create_response(
    form_id: UUID, payload: dict, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    payload["form_id"] = str(form_id)
    return await response_service.create(payload)


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
    return await response_service.find(form_id, skip=skip, limit=limit)


@form_router.get(
    "/responses/{response_id}", response_model=APIResponse, summary="Get response by ID"
)
async def get_response(
    response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await response_service.get(response_id)


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
    return await response_service.update(response_id, payload)


@form_router.delete(
    "/responses/{response_id}",
    response_model=APIResponse,
    summary="Delete response by ID",
)
async def delete_response(
    response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await response_service.delete(response_id)


# --- Form Section Responses CRUD ---
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
    return await section_response_service.create(payload)


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
    return await section_response_service.find(response_id, skip=skip, limit=limit)


@form_router.get(
    "/section-responses/{section_response_id}",
    response_model=APIResponse,
    summary="Get section response by ID",
)
async def get_section_response(
    section_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_response_service.get(section_response_id)


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
    return await section_response_service.update(section_response_id, payload)


@form_router.delete(
    "/section-responses/{section_response_id}",
    response_model=APIResponse,
    summary="Delete section response by ID",
)
async def delete_section_response(
    section_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await section_response_service.delete(section_response_id)


# --- Form Question Responses CRUD ---
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
    return await question_response_service.create(payload)


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
    return await question_response_service.find(
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
    return await question_response_service.get(question_response_id)


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
    return await question_response_service.update(question_response_id, payload)


@form_router.delete(
    "/question-responses/{question_response_id}",
    response_model=APIResponse,
    summary="Delete question response by ID",
)
async def delete_question_response(
    question_response_id: UUID, _: Annotated[dict[str, Any], Depends(require_auth)]
):
    return await question_response_service.delete(question_response_id)

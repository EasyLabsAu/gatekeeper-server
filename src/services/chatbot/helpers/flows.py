from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.forms import (
    FormFieldTypes,
    FormQuestionResponses,
    FormResponses,
    Forms,
    FormSectionResponses,
)
from src.services.chatbot.helpers.session import SessionManager


class Question:
    def __init__(
        self,
        text: str,
        field_type: str | None,
        required: bool | None,
        options: list[str] | None,
        question_id: UUID | None,
        section_id: UUID | None,
        key: str | None = None,  # Make key optional or remove if not used
        validation: Callable[[str], bool] | None = None,
        extractor: Callable[[str], Any] | None = None,
        success_message: str | None = None,
    ):
        self.text = text
        self.field_type = field_type
        self.required = required
        self.options = options
        self.question_id = question_id
        self.section_id = section_id
        self.key = key
        self.validation = validation
        self.extractor = extractor
        self.success_message = success_message


class ConversationFlow:
    def __init__(self, questions: list[Question], completion_message: str):
        self.questions = questions
        self.completion_message = completion_message
        self.current_question_index = 0
        self.is_active = True

    def get_current_question(self) -> Question | None:
        if self.is_active and self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def process_answer(self, answer: str, context: dict[str, Any]) -> str | None:
        question = self.get_current_question()
        if not question:
            self.deactivate()
            return None

        extracted_value = answer
        if question.extractor:
            extracted_value = question.extractor(answer)
            if not extracted_value:
                return f"I didn't quite catch that. {question.text}"

        if question.validation and not question.validation(extracted_value):
            return f"That doesn't right. {question.text}"

        if question.key is not None:
            context[question.key] = extracted_value
        if question.success_message:
            print(f"Chatbot: {question.success_message.format(**context)}")

        self.current_question_index += 1
        if self.current_question_index >= len(self.questions):
            self.deactivate()
            context["lead_captured"] = True
            return self.completion_message.format(**context)

        next_question = self.get_current_question()
        return next_question.text if next_question else None

    @property
    def is_completed(self) -> bool:
        return self.current_question_index >= len(self.questions)

    def deactivate(self):
        self.is_active = False


class FormFlowManager:
    def __init__(self, db_session: AsyncSession, session_manager: SessionManager):
        self.db_session = db_session
        self.session_manager = session_manager

    async def start_form_conversation(
        self, session_id: str, form_id: UUID
    ) -> str | None:
        form = await self.db_session.get(Forms, form_id)
        if not form:
            return "I couldn't find that form."

        # Load questions and sections in order
        questions_data = await self.db_session.run_sync(
            lambda session: [
                question
                for section in sorted(form.sections, key=lambda s: s.order)
                for question in sorted(section.questions, key=lambda q: q.order)
            ]
        )

        if not questions_data:
            return "This form has no questions defined."

        # Create ConversationFlow questions
        conversation_questions = []
        for q_data in questions_data:
            # Use prompt if available, otherwise fallback to label
            question_text = q_data.prompt if q_data.prompt else q_data.label
            conversation_questions.append(
                Question(
                    text=question_text,
                    field_type=q_data.field_type.value,
                    required=q_data.required,
                    options=q_data.options,
                    question_id=q_data.id,
                    section_id=q_data.section_id,
                )
            )

        completion_message = f"Thank you for completing the '{form.name}' form!"
        new_flow = ConversationFlow(conversation_questions, completion_message)

        context = await self.session_manager.get_context(session_id)
        context["conversation_flow"] = new_flow
        context["current_form_id"] = str(form_id)
        context["form_responses_id"] = (
            None  # To store the main FormResponses ID once created
        )
        await self.session_manager.save_context(session_id, context)

        current_question = new_flow.get_current_question()
        return current_question.text if current_question else completion_message

    async def process_form_answer(self, session_id: str, user_input: str) -> bool:
        context = await self.session_manager.get_context(session_id)
        active_flow: ConversationFlow | None = context.get("conversation_flow")
        current_form_id_str = context.get("current_form_id")
        form_responses_id = context.get("form_responses_id")

        if not active_flow or not active_flow.is_active or not current_form_id_str:
            return False

        current_question = active_flow.get_current_question()
        if not current_question:
            return False

        validation_error = self._validate_answer(user_input, current_question)
        if validation_error:
            return False

        if not form_responses_id:
            new_form_response = FormResponses(
                form_id=UUID(current_form_id_str),
                session_id=UUID(session_id),
                submitted_at=None,
            )
            self.db_session.add(new_form_response)
            await self.db_session.commit()
            await self.db_session.refresh(new_form_response)
            context["form_responses_id"] = str(new_form_response.id)
            form_responses_id = new_form_response.id
        else:
            form_responses_id = UUID(form_responses_id)

        result = await self.db_session.scalars(
            select(FormSectionResponses).where(
                FormSectionResponses.response_id == form_responses_id,
                FormSectionResponses.section_id == current_question.section_id,
            )
        )
        section_response = result.first()

        if not section_response:
            section_id = (
                current_question.section_id
                if current_question.section_id is not None
                else UUID(int=0)
            )
            section_response = FormSectionResponses(
                response_id=form_responses_id, section_id=section_id
            )
            self.db_session.add(section_response)
            await self.db_session.commit()
            await self.db_session.refresh(section_response)

        question_response = FormQuestionResponses(
            section_response_id=section_response.id,
            question_id=current_question.question_id
            if current_question.question_id is not None
            else UUID(int=0),
            answer=user_input,
            submitted_at=None,
        )
        self.db_session.add(question_response)
        await self.db_session.commit()
        await self.db_session.refresh(question_response)

        active_flow.process_answer(user_input, context)

        await self.session_manager.save_context(session_id, context)
        return True

    async def get_next_question_text(self, session_id: str) -> str:
        context = await self.session_manager.get_context(session_id)
        active_flow: ConversationFlow | None = context.get("conversation_flow")

        if not active_flow or not active_flow.is_active:
            return "There is no active form conversation."

        if active_flow.is_completed:
            form_responses_id = context.get("form_responses_id")
            main_form_response = await self.db_session.get(
                FormResponses, UUID(form_responses_id)
            )
            if main_form_response:
                main_form_response.submitted_at = datetime.now().isoformat()
                self.db_session.add(main_form_response)
                await self.db_session.commit()
            context["conversation_flow"] = None
            context["current_form_id"] = None
            context["form_responses_id"] = None
            await self.session_manager.save_context(session_id, context)
            return active_flow.completion_message
        else:
            next_question = active_flow.get_current_question()
            return (
                next_question.text
                if next_question
                else "Something went wrong getting the next question."
            )

    def _validate_answer(self, answer: str, question: Question) -> str | None:
        if question.required and not answer.strip():
            return "This question is required."

        if (
            not answer.strip()
        ):  # If not required and empty, no further validation needed
            return None

        if question.field_type == FormFieldTypes.NUMBER.value:
            try:
                float(answer)
            except ValueError:
                return "Please enter a valid number."
        elif question.field_type == FormFieldTypes.BOOLEAN.value:
            if answer.lower() not in ["true", "false", "yes", "no"]:
                return "Please answer with 'true' or 'false' (or 'yes'/'no')."
        elif question.field_type in [
            FormFieldTypes.SINGLE_CHOICE.value,
            FormFieldTypes.MULTIPLE_CHOICE.value,
        ]:
            if question.field_type == FormFieldTypes.SINGLE_CHOICE.value:
                if question.options and answer not in question.options:
                    return f"Please choose one of the following options: {', '.join(question.options)}"
            elif question.field_type == FormFieldTypes.MULTIPLE_CHOICE.value:
                if question.options:
                    chosen_options = [opt.strip() for opt in answer.split(",")]
                    for opt in chosen_options:
                        if opt not in question.options:
                            return f"One or more of your choices are not valid. Please choose from: {', '.join(question.options)}"
        elif question.field_type == FormFieldTypes.DATETIME.value:
            try:
                datetime.fromisoformat(answer)
            except ValueError:
                return "Please enter a valid date and time in ISO format (YYYY-MM-DDTHH:MM:SS)."
        return None
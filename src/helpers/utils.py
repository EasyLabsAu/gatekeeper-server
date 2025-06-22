from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from starlette.responses import JSONResponse

T = TypeVar("T")


# Custom error class for exceptions with status code support
class APIError(Exception):
    def __init__(
        self, status_code: int = 500, error: str = "An unknown error occurred"
    ):
        self.status_code = status_code
        self.error = error

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"error": self.error, "status_code": self.status_code},
        )


# Standardized response model for consistent API responses
class APIResponse(BaseModel, Generic[T]):
    data: T | None = None
    message: str | None = None
    meta: dict[str, Any] | None = None

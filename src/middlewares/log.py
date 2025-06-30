import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.helpers.logger import Logger

logger = Logger(__name__)


class LogRequests(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Get client IP, handling potential proxy headers
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # Log request
        logger.info(
            "Incoming request | %s %s | Client IP: %s",
            request.method,
            request.url.path,
            client_ip,
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            logger.info(
                "Request completed | %s %s | Status: %d | Time: %.3fs | Client IP: %s",
                request.method,
                request.url.path,
                response.status_code,
                process_time,
                client_ip,
            )
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed | %s %s | Error: %s | Time: %.3fs | Client IP: %s",
                request.method,
                request.url.path,
                str(e),
                process_time,
                client_ip,
            )
            raise

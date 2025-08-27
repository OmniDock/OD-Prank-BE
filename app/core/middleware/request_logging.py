import time
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import console_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):

    LOGGING_ENABLED = False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:

        if not self.LOGGING_ENABLED:
            return await call_next(request)

        start = time.perf_counter()

        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip: Optional[str] = request.headers.get("x-forwarded-for")
        if not client_ip and request.client:
            client_ip = request.client.host

        logger = console_logger.bind(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            query=request.url.query or None,
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info("request.start")

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning("request.end", status_code=500, duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request.end",
            status_code=status_code,
            duration_ms=duration_ms,
            bytes_out=response.headers.get("content-length"),
        )
        return response
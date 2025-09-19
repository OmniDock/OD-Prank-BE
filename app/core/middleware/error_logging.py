from typing import Optional, Dict, Any
import uuid

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import console_logger
from app.core.config import settings


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id: Optional[str] = getattr(getattr(request, "state", None), "request_id", None)
        if not request_id:
            # Ensure we always have a request id, even if request logging is disabled
            request_id = str(uuid.uuid4())
            try:
                request.state.request_id = request_id
            except Exception:
                pass

        try:
            return await call_next(request)

        except HTTPException as exc:
            logger = console_logger.bind(
                request_id=request_id,
                method=request.method,
                path=str(request.url.path),
                status_code=exc.status_code,
            )
            # Include stack trace for HTTP errors as well for complete diagnostics
            logger.warning("http_exception", detail=str(exc.detail), exc_info=True)

            payload: Dict[str, Any] = {"detail": exc.detail, "request_id": request_id}
            headers = dict(exc.headers or {})
            headers["X-Request-ID"] = request_id or ""
            return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)

        except Exception as exc:
            logger = console_logger.bind(
                request_id=request_id,
                method=request.method,
                path=str(request.url.path),
            )
            logger.error("unhandled_exception", exc_info=True)

            payload: Dict[str, Any] = {"detail": "Internal Server Error", "request_id": request_id}
            # In development, provide more diagnostics in the response
            if settings.DEBUG:
                payload.update({
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                })
            return JSONResponse(status_code=500, content=payload, headers={"X-Request-ID": request_id or ""})
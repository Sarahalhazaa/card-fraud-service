"""The FastAPI app: start-up (load the model once), tracing, and one error shape for everything.

    uvicorn card_fraud.api.app:create_app --factory
"""
import logging
import time
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from card_fraud.api.routes import router
from card_fraud.composition import build_scorer
from card_fraud.config import ServiceSettings
from card_fraud.domain.payment import V_NAMES, Payment

log = logging.getLogger("card_fraud")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model ONCE, here: visible, timed, and able to fail loudly."""
    settings = ServiceSettings()
    logging.basicConfig(level=settings.log_level)
    app.state.settings = settings

    t0 = time.perf_counter()
    scorer, card = build_scorer(settings)  # fails fast if the model file is missing
    scorer.assess(Payment(time_seconds=0.0, amount=1.0, v=(0.0,) * len(V_NAMES)))  # warm-up
    app.state.scorer, app.state.model_card = scorer, card
    log.info("model ready: version=%s review=%.2f block=%.2f seconds=%.2f",
             card.model_version, scorer.policy.review_threshold,
             scorer.policy.block_threshold, time.perf_counter() - t0)
    yield
    log.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Card Fraud Scoring Service",
        version="1.0.0",
        description="Scores one card payment, decides allow / review / block, and gives the top "
                    "reasons. Teaching model trained on 2013 data: never act without a human check.",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/v1")

    @app.middleware("http")
    async def trace_and_time(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", uuid.uuid4().hex[:16])[:64]
        request.state.trace_id = trace_id
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time-Ms"] = str(round((time.perf_counter() - t0) * 1000, 1))
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Field names and problems only: never echo the values the client sent.
        details = [{"field": ".".join(str(p) for p in err["loc"][1:]) or "body", "problem": err["msg"]}
                   for err in exc.errors()]
        return _error(request, 422, "INVALID_REQUEST", "Request body failed validation", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 503: "MODEL_UNAVAILABLE"}.get(
            exc.status_code, "HTTP_ERROR")
        return _error(request, exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(ValueError)
    async def domain_rejected(request: Request, exc: ValueError):
        # The domain refused the payment (a rule the schema does not cover).
        return _error(request, 400, "PAYMENT_REJECTED", str(exc))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        # Never leak stack traces to clients; always give them a trace_id.
        log.error("unhandled exception trace_id=%s", _trace_id(request), exc_info=exc)
        return _error(request, 500, "INTERNAL_ERROR", "Unexpected error; contact support with trace_id")

    return app


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "unknown")


def _error(request: Request, status: int, code: str, message: str,
           headers: Mapping[str, str] | None = None, **extra: object) -> JSONResponse:
    """One error shape for every failure: {"error": {code, message, trace_id}}."""
    trace_id = _trace_id(request)
    body = {"code": code, "message": message, "trace_id": trace_id, **extra}
    all_headers = {"X-Trace-Id": trace_id, **(headers or {})}
    return JSONResponse(status_code=status, content={"error": body}, headers=all_headers)

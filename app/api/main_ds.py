"""FastAPI application factory for the modular monolith."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.errors.problem_ds import ProblemDetails
from app.api.middleware.request_id_ds import RequestIdMiddleware
from app.api.routers import classification_ds as classification
from app.api.routers import health_ds as health
from app.api.routers import identity_ds as identity
from app.api.routers import imports_ds as imports
from app.api.routers import review_ds as review
from app.api.routers import tasks_ds as tasks
from app.api.routers import templates_ds as templates
from app.api.routers import workbench_ds as workbench
from app.services.container import Services


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="Industrial Form API", version="0.1.0")
    app.state.services = services
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(identity.router)
    app.include_router(imports.router)
    app.include_router(classification.router)
    app.include_router(review.router)
    app.include_router(workbench.router)
    app.include_router(templates.router)
    app.include_router(tasks.router)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        detail = error.detail if isinstance(error.detail, dict) else {"detail": str(error.detail)}
        problem = ProblemDetails(
            title="Request failed",
            status=error.status_code,
            code=str(detail.pop("code", "HTTP_ERROR")),
            detail=str(detail.pop("detail", "The request could not be completed.")),
            request_id=request_id,
        )
        return JSONResponse(
            status_code=problem.status,
            content={**problem.model_dump(), **detail},
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, error: Exception) -> JSONResponse:
        del error
        request_id = getattr(request.state, "request_id", "unknown")
        problem = ProblemDetails(
            title="Internal server error",
            status=500,
            code="INTERNAL_ERROR",
            detail="An unexpected error occurred.",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    return app

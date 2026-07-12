"""FastAPI application factory for the modular monolith."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.errors.problem import ProblemDetails
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.routers import health, identity
from app.services.container import Services


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="Industrial Form API", version="0.1.0")
    app.state.services = services
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(identity.router)

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

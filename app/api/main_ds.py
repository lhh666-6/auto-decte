"""FastAPI application factory for the modular monolith."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.errors.problem_ds import ProblemDetails
from app.api.middleware.request_id_ds import RequestIdMiddleware
from app.api.routers import classification_ds as classification
from app.api.routers import exports_ds as exports
from app.api.routers import health_ds as health
from app.api.routers import identity_ds as identity
from app.api.routers import imports_ds as imports
from app.api.routers import master_data_ds as master_data
from app.api.routers import mobile_ds as mobile
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
    app.include_router(master_data.router)
    app.include_router(classification.router)
    app.include_router(exports.router)
    app.include_router(review.router)
    app.include_router(workbench.router)
    app.include_router(templates.router)
    app.include_router(tasks.router)
    app.include_router(mobile.router)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        detail = error.detail if isinstance(error.detail, dict) else {"detail": str(error.detail)}
        problem = ProblemDetails(
            title="请求未能完成",
            status=error.status_code,
            code=str(detail.pop("code", "HTTP_ERROR")),
            detail=str(detail.pop("detail", "当前请求无法继续，请检查输入后重试。")),
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
            title="服务暂时无法完成请求",
            status=500,
            code="INTERNAL_ERROR",
            detail="服务发生异常，请稍后重试；如问题持续，请记录请求编号以便追溯。",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    return app

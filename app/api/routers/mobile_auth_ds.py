"""Cookie-based mobile authentication routes."""

import secrets
from typing import cast

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.api.schemas.mobile_ds import LoginRequest, LoginResponse, SessionResponse
from app.application.mobile_identity_ds import (
    AccountLocked,
    AuthenticationError,
    MobileActor,
)
from app.services.container import Services

SESSION_COOKIE = "mobile_session"
CSRF_COOKIE = "mobile_csrf"

router = APIRouter(prefix="/auth")


def _services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


def require_mobile_actor(request: Request) -> MobileActor:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "SESSION_REQUIRED", "detail": "请先登录。"},
        )
    actor = _services(request).mobile_identity.verify_session(token)
    if actor is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "SESSION_EXPIRED", "detail": "会话已失效，请重新登录。"},
        )
    return actor


def require_csrf(request: Request, submitted_token: str | None) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if (
        not cookie_token
        or not submitted_token
        or not secrets.compare_digest(cookie_token, submitted_token)
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CSRF_VALIDATION_FAILED",
                "detail": "请求来源校验失败，请刷新页面后重试。",
            },
        )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    services = _services(request)
    try:
        actor, token = services.mobile_identity.authenticate(
            body.employee_code,
            body.pin,
            body.device_id,
        )
    except AccountLocked as error:
        raise HTTPException(
            status_code=429,
            detail={"code": "ACCOUNT_LOCKED", "detail": str(error)},
        ) from error
    except AuthenticationError as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTHENTICATION_FAILED", "detail": str(error)},
        ) from error
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=services.settings.environment == "production",
        samesite="lax",
        path="/api/v1/mobile",
    )
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(24),
        httponly=False,
        secure=services.settings.environment == "production",
        samesite="lax",
        path="/api/v1/mobile",
    )
    return LoginResponse(
        employee_name=actor.employee_name,
        employee_code=actor.employee_code,
        team_name=actor.team_name,
        position=actor.position,
        roles=actor.roles,
    )


@router.get("/session", response_model=SessionResponse)
def session(request: Request) -> SessionResponse:
    actor = require_mobile_actor(request)
    return SessionResponse(
        employee_name=actor.employee_name,
        employee_code=actor.employee_code,
        team_name=actor.team_name,
        position=actor.position,
        roles=actor.roles,
        allowed_form_types=actor.allowed_form_types,
        allowed_processes=actor.allowed_processes,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, str]:
    require_csrf(request, x_csrf_token)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _services(request).mobile_identity.revoke_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/api/v1/mobile")
    response.delete_cookie(CSRF_COOKIE, path="/api/v1/mobile")
    return {"status": "ok"}

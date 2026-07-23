"""Cookie authentication shared by the three Web management workspaces."""

from __future__ import annotations

import secrets
from typing import cast

from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.api.schemas.web_workspaces_ds import WebLoginRequest, WebSessionResponse
from app.application.mobile_identity_ds import (
    AccountLocked,
    AuthenticationError,
    MobileActor,
)
from app.modules.identity_access.web_policy_ds import WebActor, workspace_roles
from app.services.container import Services

SESSION_COOKIE = "web_session"
CSRF_COOKIE = "web_csrf"

router = APIRouter(prefix="/api/v1/web/auth", tags=["web-auth"])


def _services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


def _as_web_actor(actor: MobileActor) -> WebActor:
    return WebActor(
        employee_code=actor.employee_code,
        employee_name=actor.employee_name,
        workspace_roles=workspace_roles(actor.roles),
        factory_id=actor.factory_id,
        factory_name=actor.factory_name,
    )


def _session_response(actor: WebActor) -> WebSessionResponse:
    return WebSessionResponse(
        employee_code=actor.employee_code,
        employee_name=actor.employee_name,
        workspace_role=actor.primary_role.value,
        workspace_roles=sorted(role.value for role in actor.workspace_roles),
        factory_id=actor.factory_id,
        factory_name=actor.factory_name,
        landing_path=actor.landing_path,
    )


def require_web_actor(request: Request) -> WebActor:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "WEB_SESSION_REQUIRED", "detail": "请先登录 Web 工作区。"},
        )
    identity = _services(request).mobile_identity.verify_session(token)
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "WEB_SESSION_EXPIRED", "detail": "Web 会话已失效，请重新登录。"},
        )
    actor = _as_web_actor(identity)
    if not actor.workspace_roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_REQUIRED", "detail": "当前账号没有 Web 管理角色。"},
        )
    return actor


def require_web_csrf(request: Request, submitted_token: str | None) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if (
        not cookie_token
        or not submitted_token
        or not secrets.compare_digest(cookie_token, submitted_token)
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "CSRF_VALIDATION_FAILED", "detail": "请求来源校验失败，请刷新后重试。"},
        )


def _set_csrf_cookie(response: Response, *, secure: bool) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(24),
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=WebSessionResponse)
def login(
    body: WebLoginRequest,
    request: Request,
    response: Response,
) -> WebSessionResponse:
    services = _services(request)
    try:
        identity, token = services.mobile_identity.authenticate(
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

    actor = _as_web_actor(identity)
    if not actor.workspace_roles:
        services.mobile_identity.revoke_session(token)
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_REQUIRED", "detail": "当前账号没有 Web 管理角色。"},
        )

    secure = services.settings.environment == "production"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/v1",
    )
    _set_csrf_cookie(response, secure=secure)
    return _session_response(actor)


@router.get("/session", response_model=WebSessionResponse)
def session(request: Request, response: Response) -> WebSessionResponse:
    actor = require_web_actor(request)
    _set_csrf_cookie(
        response,
        secure=_services(request).settings.environment == "production",
    )
    return _session_response(actor)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, str]:
    require_web_csrf(request, x_csrf_token)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        _services(request).mobile_identity.revoke_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/api/v1")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"status": "ok"}

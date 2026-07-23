"""Role and factory policy for the three Web management workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WebWorkspace(StrEnum):
    ADMIN = "ADMIN"
    FINANCE = "FINANCE"
    PLANT_MANAGER = "PLANT_MANAGER"


LANDING_PATHS: dict[WebWorkspace, str] = {
    WebWorkspace.ADMIN: "/admin/overview",
    WebWorkspace.FINANCE: "/finance/overview",
    WebWorkspace.PLANT_MANAGER: "/plant/overview",
}


@dataclass(frozen=True, slots=True)
class WebActor:
    employee_code: str
    employee_name: str
    workspace_roles: frozenset[WebWorkspace]
    factory_id: str = ""
    factory_name: str = ""

    @property
    def primary_role(self) -> WebWorkspace:
        for role in (
            WebWorkspace.ADMIN,
            WebWorkspace.FINANCE,
            WebWorkspace.PLANT_MANAGER,
        ):
            if role in self.workspace_roles:
                return role
        raise ValueError("employee has no Web management role")

    @property
    def landing_path(self) -> str:
        return LANDING_PATHS[self.primary_role]


def workspace_roles(role_values: list[str]) -> frozenset[WebWorkspace]:
    allowed = {role.value: role for role in WebWorkspace}
    return frozenset(allowed[value] for value in role_values if value in allowed)


def allows_workspace(actor: WebActor, workspace: WebWorkspace) -> bool:
    return (
        WebWorkspace.ADMIN in actor.workspace_roles
        or workspace in actor.workspace_roles
    )


def resolve_plant_factory(actor: WebActor, requested_factory_id: str | None) -> str:
    """Resolve a plant view while preventing manager cross-factory access."""
    if WebWorkspace.ADMIN in actor.workspace_roles:
        factory_id = requested_factory_id or actor.factory_id
        if not factory_id:
            raise ValueError("管理员查看本厂工作区时必须选择工厂。")
        return factory_id

    if not actor.factory_id:
        raise ValueError("厂长账号尚未绑定工厂。")
    if requested_factory_id and requested_factory_id != actor.factory_id:
        raise PermissionError("厂长只能查看本厂数据。")
    return actor.factory_id

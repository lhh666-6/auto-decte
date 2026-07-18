"""Explicit local role-to-permission policy."""

from app.modules.identity_access.models_ds import Actor, Permission, Role

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.OPERATOR: frozenset(
        {
            Permission.FORM_READ,
            Permission.FORM_IMPORT,
            Permission.FORM_CLASSIFY,
            Permission.FORM_EDIT_DRAFT,
            Permission.REVIEW_ACQUIRE,
            Permission.EVIDENCE_IMAGE_READ,
            Permission.MASTER_DATA_READ,
            Permission.TASK_READ,
        }
    ),
    Role.REVIEWER: frozenset(
        {
            Permission.FORM_READ,
            Permission.FORM_EDIT_DRAFT,
            Permission.REVIEW_ACQUIRE,
            Permission.REVIEW_CONFIRM,
            Permission.REVIEW_CORRECT,
            Permission.REVIEW_RETURN,
            Permission.REVIEW_VOID,
            Permission.AUDIT_READ,
            Permission.EVIDENCE_IMAGE_READ,
            Permission.EVIDENCE_AUDIO_READ,
            Permission.MASTER_DATA_READ,
            Permission.TASK_READ,
        }
    ),
    Role.FINANCE: frozenset(
        {
            Permission.FORM_READ,
            Permission.EXPORT_PREVIEW,
            Permission.EXPORT_CREATE,
            Permission.EXPORT_DOWNLOAD,
            Permission.AUDIT_READ,
            Permission.EVIDENCE_IMAGE_READ,
            Permission.MASTER_DATA_READ,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.FORM_READ,
            Permission.AUDIT_READ,
            Permission.EVIDENCE_IMAGE_READ,
            Permission.EVIDENCE_AUDIO_READ,
            Permission.MASTER_DATA_READ,
            Permission.TASK_READ,
        }
    ),
}


class PermissionPolicy:
    def allows(self, actor: Actor, permission: Permission) -> bool:
        return actor.authenticated and (
            actor.local_full_access
            or any(permission in ROLE_PERMISSIONS[role] for role in actor.roles)
        )

    def require(self, actor: Actor, permission: Permission) -> None:
        if not self.allows(actor, permission):
            raise PermissionError(
                "当前操作未获得授权。请确认登录状态或联系管理员配置业务权限。"
            )

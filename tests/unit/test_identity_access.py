from app.modules.identity_access.models import Actor, Permission, Role
from app.modules.identity_access.policy import PermissionPolicy


def test_operator_cannot_confirm_and_reviewer_can_confirm() -> None:
    policy = PermissionPolicy()
    operator = Actor("operator-1", frozenset({Role.OPERATOR}))
    reviewer = Actor("reviewer-1", frozenset({Role.REVIEWER}))

    assert policy.allows(operator, Permission.REVIEW_CONFIRM) is False
    assert policy.allows(reviewer, Permission.REVIEW_CONFIRM) is True


def test_auditor_is_read_only_and_finance_can_export() -> None:
    policy = PermissionPolicy()
    auditor = Actor("auditor-1", frozenset({Role.AUDITOR}))
    finance = Actor("finance-1", frozenset({Role.FINANCE}))

    assert policy.allows(auditor, Permission.AUDIT_READ) is True
    assert policy.allows(auditor, Permission.REVIEW_CORRECT) is False
    assert policy.allows(finance, Permission.EXPORT_CREATE) is True
    assert policy.allows(finance, Permission.REVIEW_VOID) is False


def test_admin_can_force_release_and_local_identity_defaults_to_configured_role() -> None:
    from app.modules.identity_access.local import LocalIdentityProvider

    policy = PermissionPolicy()
    admin = Actor("admin-1", frozenset({Role.ADMIN}))
    provider = LocalIdentityProvider("operator-2", ("OPERATOR",))

    assert policy.allows(admin, Permission.REVIEW_FORCE_RELEASE) is True
    assert provider.current_actor().roles == frozenset({Role.OPERATOR})

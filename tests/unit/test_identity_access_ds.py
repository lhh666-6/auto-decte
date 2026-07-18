from app.modules.identity_access.models_ds import Actor, Permission, Role
from app.modules.identity_access.policy_ds import PermissionPolicy


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
    assert policy.allows(finance, Permission.EXPORT_DOWNLOAD) is True
    assert policy.allows(auditor, Permission.EXPORT_DOWNLOAD) is False
    assert policy.allows(finance, Permission.REVIEW_VOID) is False


def test_admin_can_force_release_and_local_identity_defaults_to_configured_role() -> None:
    from app.modules.identity_access.local_ds import LocalIdentityProvider

    policy = PermissionPolicy()
    admin = Actor("admin-1", frozenset({Role.ADMIN}))
    provider = LocalIdentityProvider("operator-2", ("OPERATOR",))

    assert policy.allows(admin, Permission.REVIEW_FORCE_RELEASE) is True
    assert provider.current_actor().roles == frozenset({Role.OPERATOR})


def test_local_full_access_operator_can_use_every_business_permission() -> None:
    from app.modules.identity_access.local_ds import LocalIdentityProvider

    policy = PermissionPolicy()
    actor = LocalIdentityProvider(
        "local-operator",
        ("OPERATOR",),
        full_access=True,
    ).current_actor()

    assert actor.roles == frozenset({Role.OPERATOR})
    assert all(policy.allows(actor, permission) for permission in Permission)


def test_authenticated_operator_still_uses_the_role_permission_matrix() -> None:
    policy = PermissionPolicy()
    operator = Actor("operator-1", frozenset({Role.OPERATOR}))

    assert policy.allows(operator, Permission.FORM_IMPORT) is True
    assert policy.allows(operator, Permission.TEMPLATE_CREATE_VERSION) is False
    assert policy.allows(operator, Permission.EXPORT_CREATE) is False

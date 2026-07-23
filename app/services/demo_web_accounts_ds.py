"""Install development-only Web workspace test accounts."""

from dataclasses import dataclass

from app.adapters.database.mobile_identity_repository_ds import (
    SqlAlchemyMobileIdentityRepository,
)
from app.modules.master_data.facade_ds import MasterDataFacade
from app.modules.master_data.models_ds import (
    MasterDataCatalog,
    MasterDataNotFound,
)

DEFAULT_TEST_PIN = "2468"


@dataclass(frozen=True, slots=True)
class DemoWebAccount:
    employee_code: str
    employee_name: str
    position: str
    workspace_role: str


DEMO_WEB_ACCOUNTS = (
    DemoWebAccount("GLY001", "系统管理员", "系统管理员", "ADMIN"),
    DemoWebAccount("CW001", "孙财务", "财务", "FINANCE"),
)


def install_demo_web_accounts(
    master_data: MasterDataFacade,
    identity_repository: SqlAlchemyMobileIdentityRepository,
) -> None:
    """Create missing demo accounts and add Web roles without replacing user data."""
    for account in DEMO_WEB_ACCOUNTS:
        try:
            master_data.get(MasterDataCatalog.EMPLOYEES, account.employee_code)
        except MasterDataNotFound:
            master_data.create(
                MasterDataCatalog.EMPLOYEES,
                account.employee_code,
                account.employee_name,
                {},
                "development-seed",
                "Install development Web test account",
            )

        if identity_repository.get_credential(account.employee_code) is None:
            identity_repository.set_credential(
                account.employee_code,
                DEFAULT_TEST_PIN,
            )

        current = identity_repository.get_access_profile(account.employee_code)
        roles = sorted(
            set(current.roles if current is not None else [])
            | {account.workspace_role}
        )
        identity_repository.set_access_profile(
            account.employee_code,
            team_id=current.team_id if current is not None else "WEB-DEMO",
            team_name=current.team_name if current is not None else "Web 测试账户",
            position=current.position if current is not None else account.position,
            roles=roles,
            allowed_form_types=(
                current.allowed_form_types if current is not None else []
            ),
            allowed_processes=(
                current.allowed_processes if current is not None else []
            ),
            active=current.active if current is not None else True,
            factory_id=current.factory_id if current is not None else "",
            factory_name=current.factory_name if current is not None else "",
        )

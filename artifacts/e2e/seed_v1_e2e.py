"""V1 Final Acceptance E2E Seed Script.

Prerequisites: alembic upgrade head on the target database.
Usage: python artifacts/e2e/seed_v1_e2e.py <db_path>

Seeds: test factories, accounts, roles, business preset, field registry,
managed form definitions, versions, and plant activations.
Idempotent — safe to run repeatedly.
"""

import sys
from datetime import UTC, datetime


def seed(db_path: str) -> dict:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{db_path}")
    now = datetime.now(UTC)

    from app.adapters.database.models import (
        BambooFactoryRow,
        BambooRoleDefinitionRow,
        BusinessPresetVersionRow,
        EmployeeBambooAssignmentRow,
        FormPlantActivationRow,
        ManagedFormDefinitionRow,
        ManagedFormVersionRow,
        MasterDataRecordRow,
        MobileAccessProfileRow,
        MobileCredentialRow,
    )
    from app.application.mobile_identity_ds import hash_pin
    from app.modules.electronic_forms.v1_form_seeds_ds import (
        install_v1_business_form_seeds,
    )
    from app.modules.payroll_rules.field_registry_seed import (
        install_v1_field_registry,
    )

    results: dict = {}

    with Session(engine) as session, session.begin():
        # ── 1. Factories ──────────────────────────────────────
        factories = {
            "FACTORY_A": "测试工厂A",
            "FACTORY_B": "测试工厂B",
        }
        for fid, fname in factories.items():
            existing = session.get(BambooFactoryRow, fid)
            if existing is None:
                session.add(BambooFactoryRow(
                    factory_id=fid, code=fid, name=fname,
                    active=True, created_at=now, updated_at=now,
                ))
        results["factories"] = len(factories)

        # ── 2. Role Definitions ───────────────────────────────
        roles = [
            ("SORT_OPERATOR", "分选工", "PRODUCTION"),
            ("DIPPING_OPERATOR", "浸胶工", "PRODUCTION"),
            ("DRYING_RACK_OPERATOR", "干燥工", "PRODUCTION"),
            ("INSPECTOR", "检测人", "QUALITY"),
            ("SUPERVISOR", "主管", "QUALITY"),
            ("PLANT_MANAGER", "厂长", "MANAGEMENT"),
            ("FINANCE_APPROVER", "财务审批", "FINANCE"),
            ("SYSTEM_ADMIN", "系统管理员", "ADMIN"),
        ]
        for role_code, display, cat in roles:
            existing = session.get(BambooRoleDefinitionRow, role_code)
            if existing is None:
                session.add(BambooRoleDefinitionRow(
                    role_code=role_code, display_name=display,
                    category=cat, active=True, self_requestable=True,
                ))
        results["roles"] = len(roles)

        # ── 3. Test Accounts ──────────────────────────────────
        PIN = "1234"
        pin = hash_pin(PIN)
        accounts = [
            ("ADMIN001", "管理员", "FACTORY_A", "SYSTEM_ADMIN"),
            ("FIN001", "财务", "FACTORY_A", "FINANCE_APPROVER"),
            ("PLANT_A001", "厂长A", "FACTORY_A", "PLANT_MANAGER"),
            ("PLANT_B001", "厂长B", "FACTORY_B", "PLANT_MANAGER"),
            ("SORT001", "分选工", "FACTORY_A", "SORT_OPERATOR"),
            ("DIP001", "浸胶工", "FACTORY_A", "DIPPING_OPERATOR"),
            ("DRY001", "干燥工", "FACTORY_A", "DRYING_RACK_OPERATOR"),
            ("INSPECT001", "检测人", "FACTORY_A", "INSPECTOR"),
            ("SUP001", "主管", "FACTORY_A", "SUPERVISOR"),
        ]
        created = 0
        for code, name, factory, role in accounts:
            # Master data
            existing = session.get(MasterDataRecordRow, ("employees", code))
            if existing is None:
                session.add(MasterDataRecordRow(
                    catalog="employees", code=code, display_name=name,
                    active=True, created_at=now, updated_at=now,
                ))
            # Credential
            from app.adapters.database.models import MobileCredentialRow
            existing_cred = session.get(MobileCredentialRow, ("employees", code))
            if existing_cred is None:
                session.add(MobileCredentialRow(
                    employee_catalog="employees", employee_code=code,
                    pin_salt=pin.salt, pin_hash=pin.hash_value,
                    failed_attempts=0, locked_until=None, revision=1,
                ))
            # AccessProfile
            existing_prof = session.scalar(
                select(MobileAccessProfileRow).where(
                    MobileAccessProfileRow.employee_code == code
                )
            )
            if existing_prof is None:
                session.add(MobileAccessProfileRow(
                    profile_id=f"PROF-{code}",
                    employee_catalog="employees", employee_code=code,
                    display_name=name, factory_id=factory, factory_name=factory,
                    position=role, roles=[role],
                    active=True, account_state="ACTIVE",
                    created_at=now, updated_at=now,
                ))
            # Assignment
            existing_asgn = session.scalar(
                select(EmployeeBambooAssignmentRow).where(
                    EmployeeBambooAssignmentRow.employee_code == code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                )
            )
            if existing_asgn is None:
                import uuid
                session.add(EmployeeBambooAssignmentRow(
                    assignment_id=f"ASGN-{uuid.uuid4().hex[:12].upper()}",
                    employee_catalog="employees", employee_code=code,
                    factory_id=factory, role_code=role, position=role,
                    status="ACTIVE", effective_at=now, created_at=now, updated_at=now,
                ))
            created += 1
        results["accounts"] = created

    # ── 4. Business Seeds (separate sessions) ─────────────────
    install_v1_field_registry(engine)
    results["field_registry"] = "seeded"

    install_v1_business_form_seeds(engine)
    results["business_forms"] = "seeded"

    # ── 5. Form Plant Activation ──────────────────────────────
    with Session(engine) as session, session.begin():
        import uuid
        # Activate SORTING V1 for FACTORY_A
        sv = session.scalar(
            select(ManagedFormVersionRow).join(
                ManagedFormDefinitionRow,
                ManagedFormDefinitionRow.definition_id == ManagedFormVersionRow.definition_id,
            ).where(
                ManagedFormDefinitionRow.form_key == "SORTING",
                ManagedFormVersionRow.status == "APPROVED",
            ).order_by(ManagedFormVersionRow.version.desc()).limit(1)
        )
        if sv:
            existing_act = session.scalar(
                select(FormPlantActivationRow).where(
                    FormPlantActivationRow.form_version_id == sv.version_id,
                    FormPlantActivationRow.plant_id == "FACTORY_A",
                )
            )
            if existing_act is None:
                session.add(FormPlantActivationRow(
                    activation_id=f"ACT-{uuid.uuid4().hex[:12].upper()}",
                    form_version_id=sv.version_id,
                    plant_id="FACTORY_A",
                    status="ACTIVE",
                    activated_by="ADMIN001",
                    activated_at=now,
                ))
            results["sorting_activation"] = "FACTORY_A"

        # Activate DIPPING_DRYING V1 for FACTORY_A
        dv = session.scalar(
            select(ManagedFormVersionRow).join(
                ManagedFormDefinitionRow,
                ManagedFormDefinitionRow.definition_id == ManagedFormVersionRow.definition_id,
            ).where(
                ManagedFormDefinitionRow.form_key == "DIPPING_DRYING",
                ManagedFormVersionRow.status == "APPROVED",
            ).order_by(ManagedFormVersionRow.version.desc()).limit(1)
        )
        if dv:
            existing_act = session.scalar(
                select(FormPlantActivationRow).where(
                    FormPlantActivationRow.form_version_id == dv.version_id,
                    FormPlantActivationRow.plant_id == "FACTORY_A",
                )
            )
            if existing_act is None:
                session.add(FormPlantActivationRow(
                    activation_id=f"ACT-{uuid.uuid4().hex[:12].upper()}",
                    form_version_id=dv.version_id,
                    plant_id="FACTORY_A",
                    status="ACTIVE",
                    activated_by="ADMIN001",
                    activated_at=now,
                ))
            results["dipping_activation"] = "FACTORY_A"

    results["status"] = "complete"
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python artifacts/e2e/seed_v1_e2e.py <db_path>")
        sys.exit(1)
    result = seed(sys.argv[1])
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("E2E Seed: COMPLETE")

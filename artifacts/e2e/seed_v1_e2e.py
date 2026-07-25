"""V1 E2E Seed — idempotent, creates test accounts and activates business forms.

Usage: .venv/Scripts/python.exe artifacts/e2e/seed_v1_e2e.py <db_path>
"""
import sys
from datetime import UTC, datetime
from uuid import uuid4


def seed(db_path: str) -> dict:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{db_path}")
    now = datetime.now(UTC)
    from app.application.mobile_identity_ds import hash_pin
    from app.adapters.database.models import (
        BambooFactoryRow, BambooRoleDefinitionRow,
        EmployeeBambooAssignmentRow,
        FormPlantActivationRow,
        ManagedFormDefinitionRow, ManagedFormVersionRow,
        MasterDataRecordRow,
        MobileAccessProfileRow, MobileCredentialRow,
    )
    from app.modules.electronic_forms.v1_form_seeds_ds import install_v1_business_form_seeds
    from app.modules.payroll_rules.field_registry_seed import install_v1_field_registry

    # ── Install business seeds first (idempotent) ──
    install_v1_field_registry(engine)
    install_v1_business_form_seeds(engine)

    result: dict = {}

    with Session(engine) as session, session.begin():
        # ── Factories ──
        for fid, fname in [("FACTORY_A", "测试工厂A"), ("FACTORY_B", "测试工厂B")]:
            if session.get(BambooFactoryRow, fid) is None:
                session.add(BambooFactoryRow(
                    factory_id=fid, code=fid, name=fname,
                    active=True, revision=1, created_at=now, updated_at=now,
                ))
        result["factories"] = 2

        # ── Roles ──
        role_defs = [
            ("SORT_OPERATOR", "分选工", "PRODUCTION"),
            ("DIPPING_OPERATOR", "浸胶工", "PRODUCTION"),
            ("DRYING_RACK_OPERATOR", "干燥工", "PRODUCTION"),
            ("INSPECTOR", "检测人", "QUALITY"),
            ("SUPERVISOR", "主管", "QUALITY"),
            ("PLANT_MANAGER", "厂长", "MANAGEMENT"),
            ("FINANCE_APPROVER", "财务审批", "FINANCE"),
            ("SYSTEM_ADMIN", "系统管理员", "ADMIN"),
        ]
        for rc, dn, cat in role_defs:
            if session.get(BambooRoleDefinitionRow, rc) is None:
                session.add(BambooRoleDefinitionRow(
                    role_code=rc, display_name=dn, category=cat,
                    self_requestable=True, active=True, revision=1,
                ))
        result["roles"] = len(role_defs)

        # ── Accounts (PIN = 1234) ──
        pin_salt, pin_hash = hash_pin("1234")
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
            # MasterDataRecordRow
            if session.get(MasterDataRecordRow, ("employees", code)) is None:
                session.add(MasterDataRecordRow(
                    catalog="employees", code=code, display_name=name,
                    attributes={}, active=True, revision=1,
                    created_at=now, updated_at=now,
                    created_by="SYSTEM", updated_by="SYSTEM",
                ))
            # MobileCredentialRow
            if session.get(MobileCredentialRow, ("employees", code)) is None:
                session.add(MobileCredentialRow(
                    employee_catalog="employees", employee_code=code,
                    pin_salt=pin_salt, pin_hash=pin_hash,
                    failed_attempts=0, locked_until=None,
                    revision=1, updated_at=now,
                ))
            # MobileAccessProfileRow
            prof = session.scalar(
                select(MobileAccessProfileRow).where(
                    MobileAccessProfileRow.employee_code == code
                ).limit(1)
            )
            if prof is None:
                session.add(MobileAccessProfileRow(
                    employee_catalog="employees", employee_code=code,
                    factory_id=factory, factory_name=factory,
                    position=role, roles=[role],
                    active=True, account_state="ACTIVE",
                ))
            # EmployeeBambooAssignmentRow
            asgn = session.scalar(
                select(EmployeeBambooAssignmentRow).where(
                    EmployeeBambooAssignmentRow.employee_code == code,
                    EmployeeBambooAssignmentRow.status == "ACTIVE",
                ).limit(1)
            )
            if asgn is None:
                session.add(EmployeeBambooAssignmentRow(
                    assignment_id=f"ASGN-{uuid4().hex[:12].upper()}",
                    employee_catalog="employees", employee_code=code,
                    factory_id=factory, role_code=role,
                    status="ACTIVE", effective_at=now,
                    created_by="SYSTEM", created_at=now,
                ))
            created += 1
        result["accounts"] = created

        # ── Form Plant Activation ──
        for form_key in ("SORTING", "DIPPING_DRYING"):
            v = session.scalar(
                select(ManagedFormVersionRow).join(
                    ManagedFormDefinitionRow,
                    ManagedFormDefinitionRow.definition_id == ManagedFormVersionRow.definition_id,
                ).where(
                    ManagedFormDefinitionRow.form_key == form_key,
                    ManagedFormVersionRow.status == "APPROVED",
                ).order_by(ManagedFormVersionRow.version.desc()).limit(1)
            )
            if v:
                act = session.scalar(
                    select(FormPlantActivationRow).where(
                        FormPlantActivationRow.form_version_id == v.version_id,
                        FormPlantActivationRow.plant_id == "FACTORY_A",
                    ).limit(1)
                )
                if act is None:
                    session.add(FormPlantActivationRow(
                        activation_id=f"ACT-{uuid4().hex[:12].upper()}",
                        form_version_id=v.version_id,
                        plant_id="FACTORY_A", status="ACTIVE",
                        activated_by="ADMIN001", activated_at=now,
                        updated_by="ADMIN001", updated_at=now,
                    ))
        result["activations"] = "FACTORY_A:SORTING+DIPPING_DRYING"

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python artifacts/e2e/seed_v1_e2e.py <db_path>")
        sys.exit(1)
    r = seed(sys.argv[1])
    for k, v in r.items():
        print(f"  {k}: {v}")
    print("E2E Seed: COMPLETE")

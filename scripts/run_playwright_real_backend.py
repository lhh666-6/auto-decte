"""Seed test accounts and start the FastAPI server for real-stack Playwright tests.

Usage:
  python scripts/run_playwright_real_backend.py            # seed + run server
  python scripts/run_playwright_real_backend.py --seed-only  # seed only
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Ensure project root is on sys.path so we can import app modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.adapters.database.models import (  # noqa: E402
    BambooFactoryRow,
    BambooRoleDefinitionRow,
    EmployeeBambooAssignmentRow,
    MasterDataRecordRow,
    MobileAccessProfileRow,
    MobileCredentialRow,
)
from app.application.mobile_identity_ds import hash_pin  # noqa: E402
from app.infrastructure.database.migrations import upgrade_database  # noqa: E402
from app.infrastructure.database.sqlite_ds import create_sqlite_engine  # noqa: E402

# ---------------------------------------------------------------------------
# Paths — must match what the Settings class resolves for data_root
# Settings.database_path = data_root / "database" / "demo.db"
# ---------------------------------------------------------------------------

RUNTIME_DIR = PROJECT_ROOT / ".runtime" / "playwright-real"
DB_DIR = RUNTIME_DIR / "database"
DB_PATH = DB_DIR / "demo.db"

# Set before importing config.settings so the app uses the isolated data root.
os.environ["FORM_DEMO_DATA_ROOT"] = str(RUNTIME_DIR.resolve())

# ---------------------------------------------------------------------------
# Test account definitions
# ---------------------------------------------------------------------------

TEST_PIN = "2468"

TEST_ACCOUNTS = [
    {
        "code": "ADMIN001",
        "name": "系统管理员",
        "web_roles": ["ADMIN"],
        "factory_id": "FACTORY_ADMIN",
        "factory_name": "管理中心",
        "bamboo_role": "",
        "position": "系统管理员",
    },
    {
        "code": "FIN001",
        "name": "财务主管",
        "web_roles": ["FINANCE"],
        "factory_id": "FACTORY_ADMIN",
        "factory_name": "管理中心",
        "bamboo_role": "FINANCE_APPROVER",
        "position": "财务主管",
    },
    {
        "code": "PLANT_A001",
        "name": "张厂长",
        "web_roles": ["PLANT_MANAGER"],
        "factory_id": "PLANT_A",
        "factory_name": "甲厂",
        "bamboo_role": "PLANT_MANAGER",
        "position": "厂长",
    },
    {
        "code": "PLANT_B001",
        "name": "李厂长",
        "web_roles": ["PLANT_MANAGER"],
        "factory_id": "PLANT_B",
        "factory_name": "乙厂",
        "bamboo_role": "PLANT_MANAGER",
        "position": "厂长",
    },
    {
        "code": "SORT001",
        "name": "分选工小王",
        "web_roles": [],
        "factory_id": "PLANT_A",
        "factory_name": "甲厂",
        "bamboo_role": "SORT",
        "position": "分选操作员",
    },
]

EMPLOYEE_CATALOG = "employees"


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(UTC)


def seed(engine: Engine) -> None:
    """Create test master-data records, credentials, profiles, and assignments."""
    now = _now()

    with Session(engine) as session, session.begin():
        for acct in TEST_ACCOUNTS:
            code = acct["code"]
            name = acct["name"]
            factory_id = acct["factory_id"]
            factory_name = acct["factory_name"]
            bamboo_role = acct["bamboo_role"]
            web_roles = acct["web_roles"]
            position = acct["position"]

            # --- master_data_records ---
            session.merge(
                MasterDataRecordRow(
                    catalog=EMPLOYEE_CATALOG,
                    code=code,
                    display_name=name,
                    attributes={},
                    active=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                    created_by="playwright-seed",
                    updated_by="playwright-seed",
                )
            )

            # --- credential (PIN = 2468, scrypt-hashed) ---
            salt_hex, digest_hex = hash_pin(TEST_PIN)
            session.merge(
                MobileCredentialRow(
                    employee_catalog=EMPLOYEE_CATALOG,
                    employee_code=code,
                    pin_salt=salt_hex,
                    pin_hash=digest_hex,
                    failed_attempts=0,
                    locked_until=None,
                    revision=1,
                    updated_at=now,
                )
            )

            # --- mobile_access_profile ---
            session.merge(
                MobileAccessProfileRow(
                    employee_catalog=EMPLOYEE_CATALOG,
                    employee_code=code,
                    team_id="PLAYWRIGHT-TEAM",
                    team_name="E2E Test Team",
                    position=position,
                    roles=web_roles,
                    allowed_form_types=[],
                    allowed_processes=[],
                    factory_id=factory_id,
                    factory_name=factory_name,
                    active=True,
                )
            )

            # --- bamboo_factory ---
            session.merge(
                BambooFactoryRow(
                    factory_id=factory_id,
                    code=factory_id,
                    name=factory_name,
                    active=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
            )

            # --- bamboo_role_definition (if applicable) ---
            if bamboo_role:
                if session.get(BambooRoleDefinitionRow, bamboo_role) is None:
                    session.add(
                        BambooRoleDefinitionRow(
                            role_code=bamboo_role,
                            display_name=bamboo_role,
                            category="PRODUCTION",
                            self_requestable=False,
                            active=True,
                            revision=1,
                        )
                    )

            # --- employee_bamboo_assignment (if applicable) ---
            if bamboo_role:
                session.add(
                    EmployeeBambooAssignmentRow(
                        assignment_id=f"PW-{uuid4().hex}",
                        employee_catalog=EMPLOYEE_CATALOG,
                        employee_code=code,
                        factory_id=factory_id,
                        role_code=bamboo_role,
                        status="ACTIVE",
                        effective_at=now,
                        ended_at=None,
                        created_by="playwright-seed",
                        created_at=now,
                    )
                )

    print(f"Seeded {len(TEST_ACCOUNTS)} test accounts into {DB_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Real-stack Playwright backend")
    parser.add_argument("--seed-only", action="store_true", help="Seed and exit")
    args = parser.parse_args()

    # Ensure runtime directory
    DB_DIR.mkdir(parents=True, exist_ok=True)

    # Run Alembic migrations on the isolated DB
    print(f"Running migrations on {DB_PATH} ...")
    upgrade_database(DB_PATH)

    # Create engine and seed
    engine = create_sqlite_engine(DB_PATH)
    seed(engine)
    engine.dispose()

    if args.seed_only:
        print("Seed complete. Exiting (--seed-only).")
        return

    # The FORM_DEMO_DATA_ROOT was set at module level, so config.Settings
    # will resolve database_path to the same DB_PATH we just seeded.
    import uvicorn

    print("Starting FastAPI on http://127.0.0.1:8000 ...")
    uvicorn.run(
        "app.api.main:create_app",
        host="127.0.0.1",
        port=8000,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()

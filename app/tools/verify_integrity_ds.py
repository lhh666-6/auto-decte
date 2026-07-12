"""CLI tool: verify data integrity for the local deployment.

Usage:
    uv run python -m app.tools.verify_integrity_ds
    uv run python -m app.tools.verify_integrity_ds --json
"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine

from app.infrastructure.backup.integrity_ds import IntegrityChecker


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify industrial form demo data integrity")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument(
        "--db", default="data/database/demo.db", help="Path to SQLite database"
    )
    parser.add_argument(
        "--evidence", default="data/evidence", help="Path to evidence files"
    )
    parser.add_argument(
        "--exports", default="data/exports", help="Path to export files"
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    evidence_root = Path(args.evidence)
    exports_root = Path(args.exports)

    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    engine = create_engine(f"sqlite:///{db_path}")
    checker = IntegrityChecker(engine, evidence_root, exports_root)
    report = checker.run()

    if args.json:
        print(json.dumps({
            "exit_code": report.exit_code,
            "issues": [
                {"code": i.code, "severity": i.severity, "message": i.message, "detail": i.detail}
                for i in report.issues
            ],
            "total_forms": report.total_forms,
            "total_evidence": report.total_evidence,
            "total_exports": report.total_exports,
        }, ensure_ascii=False, indent=2))
    else:
        if report.issues:
            print(f"\nFound {len(report.issues)} issue(s):")
            for issue in report.issues:
                print(f"  [{issue.severity}] {issue.code}: {issue.message}")
                if issue.detail:
                    print(f"    {issue.detail}")
        else:
            print("No integrity issues found.")
        print(
            f"\nSummary: {report.total_forms} forms, "
            f"{report.total_evidence} evidence files, "
            f"{report.total_exports} export batches"
        )

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())

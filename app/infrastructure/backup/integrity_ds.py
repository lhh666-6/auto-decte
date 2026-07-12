"""Data integrity checker for local deployments."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, text


@dataclass
class IntegrityIssue:
    code: str
    severity: str
    message: str
    detail: str = ""


@dataclass
class IntegrityReport:
    issues: list[IntegrityIssue] = field(default_factory=list)
    total_forms: int = 0
    total_evidence: int = 0
    total_exports: int = 0

    @property
    def exit_code(self) -> int:
        return 1 if self.issues else 0


class IntegrityChecker:
    """Verify database, evidence files, and export files for consistency."""

    def __init__(self, engine: Engine, evidence_root: Path, exports_root: Path) -> None:
        self._engine = engine
        self._evidence_root = evidence_root
        self._exports_root = exports_root

    def run(self) -> IntegrityReport:
        issues: list[IntegrityIssue] = []
        total_forms = 0
        total_evidence = 0
        total_exports = 0

        with self._engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM forms"))
            total_forms = result.scalar_one()

            result = connection.execute(
                text("SELECT uri, sha256 FROM evidence_files ORDER BY file_id")
            )
            evidence_rows = result.all()
            total_evidence = len(evidence_rows)
            for uri, sha256 in evidence_rows:
                full_path = self._evidence_root / uri
                if not full_path.exists():
                    issues.append(
                        IntegrityIssue(
                            code="EVIDENCE_MISSING",
                            severity="ERROR",
                            message=f"Evidence file missing: {uri}",
                            detail=f"Expected SHA-256: {sha256}",
                        )
                    )
                else:
                    actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
                    if actual_hash != sha256:
                        issues.append(
                            IntegrityIssue(
                                code="EVIDENCE_HASH_MISMATCH",
                                severity="ERROR",
                                message=f"Evidence hash mismatch: {uri}",
                                detail=f"Expected {sha256}, got {actual_hash}",
                            )
                        )

            result = connection.execute(
                text("SELECT file_path, file_sha256 FROM export_batches ORDER BY export_batch_id")
            )
            export_rows = result.all()
            total_exports = len(export_rows)
            for file_path, file_sha256 in export_rows:
                full_path = Path(file_path)
                if not full_path.exists():
                    issues.append(
                        IntegrityIssue(
                            code="EXPORT_FILE_MISSING",
                            severity="WARNING",
                            message=f"Export file missing: {file_path}",
                            detail=f"Expected SHA-256: {file_sha256}",
                        )
                    )
                elif file_sha256:
                    actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
                    if actual_hash != file_sha256:
                        issues.append(
                            IntegrityIssue(
                                code="EXPORT_HASH_MISMATCH",
                                severity="WARNING",
                                message=f"Export hash mismatch: {file_path}",
                                detail=f"Expected {file_sha256}, got {actual_hash}",
                            )
                        )

            result = connection.execute(
                text("SELECT COUNT(*) FROM tasks WHERE status = 'RUNNING'")
            )
            running_tasks = result.scalar_one()
            if running_tasks:
                issues.append(
                    IntegrityIssue(
                        code="RUNNING_TASKS",
                        severity="WARNING",
                        message=f"{running_tasks} task(s) still in RUNNING state",
                        detail="These tasks were interrupted and need recovery.",
                    )
                )

        return IntegrityReport(
            issues=issues,
            total_forms=total_forms,
            total_evidence=total_evidence,
            total_exports=total_exports,
        )

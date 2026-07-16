from pathlib import Path

import pytest
from fastapi import FastAPI


def test_canonical_api_entrypoint_remains_importable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORM_DEMO_DATA_ROOT", str(tmp_path))
    from app.api.main import create_app

    assert isinstance(create_app(), FastAPI)

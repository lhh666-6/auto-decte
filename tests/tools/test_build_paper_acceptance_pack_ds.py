from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tools.build_paper_acceptance_pack_ds import (
    REPRESENTATIVE_KEYS,
    build_acceptance_pack,
    main,
)


def test_build_acceptance_pack_renders_print_files_manifest_and_field_record(
    tmp_path: Path,
) -> None:
    output = tmp_path / "acceptance-pack"

    manifest = build_acceptance_pack(output, print_batch="ACCEPTANCE_TEST")

    assert manifest["print_scale_percent"] == 100
    assert manifest["auto_fit_allowed"] is False
    templates = manifest["templates"]
    assert isinstance(templates, list)
    assert [item["template_key"] for item in templates] == list(REPRESENTATIVE_KEYS)
    for item in templates:
        print_file = output / item["print_file"]
        assert print_file.read_bytes().startswith(b"%PDF")
        for artifact in item["artifacts"]:
            path = output / artifact["path"]
            assert path.is_file()
            assert len(artifact["sha256"]) == 64
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == manifest
    record = (output / "FIELD_ACCEPTANCE_RECORD.md").read_text(encoding="utf-8")
    assert "PDF 打印比例为 100%" in record
    assert "卡尺或毫米尺与纸张同框照片" in record


def test_build_acceptance_pack_refuses_to_mix_with_existing_files(tmp_path: Path) -> None:
    output = tmp_path / "acceptance-pack"
    output.mkdir()
    (output / "keep.txt").write_text("user file", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        build_acceptance_pack(output, print_batch="ACCEPTANCE_TEST")


def test_cli_reports_the_generated_pack_from_a_relative_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    output = Path("acceptance-pack")

    assert main(["--output", str(output), "--print-batch", "ACCEPTANCE_CLI"]) == 0

    assert "Built 3 representative templates" in capsys.readouterr().out
    assert (output / "manifest.json").is_file()

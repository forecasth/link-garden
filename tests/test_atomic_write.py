from pathlib import Path

import pytest

import link_garden.io_utils as io_utils


def test_atomic_write_preserves_existing_file_when_replace_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "index.json"
    target.write_text('{"status":"original"}\n', encoding="utf-8")

    def fail_replace(src: str, dst: str) -> None:
        raise OSError("replace failed before commit")

    monkeypatch.setattr(io_utils.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        io_utils.atomic_write_text(target, '{"status":"new"}\n')

    assert target.read_text(encoding="utf-8") == '{"status":"original"}\n'
    assert [path.name for path in tmp_path.iterdir()] == ["index.json"]


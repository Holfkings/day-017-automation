"""Pruebas de la interfaz de línea de comandos."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fileflow.cli import main


def test_init_creates_config(tmp_path: Path):
    out = tmp_path / "ff.json"
    rc = main(["init", "--output", str(out), "--name", "Demo"])
    assert rc == 0
    assert out.is_file()
    data = json.loads(out.read_text())
    assert data["version"] == 1
    assert data["rules"]


def test_init_refuses_overwrite(tmp_path: Path):
    out = tmp_path / "ff.json"
    out.write_text("{}")
    rc = main(["init", "--output", str(out)])
    assert rc == 1


def test_version_exits(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_run_dry_run_via_cli(tmp_path: Path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "photo.jpg").write_text("x")
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "source": str(src),
        "rules": [{
            "name": "img", "match_any": [{"extension": [".jpg"]}],
            "action": {"type": "move", "target": str(tmp_path / "dest")},
        }],
    }))
    rc = main(["run", str(cfg), "--dry-run", "--quiet"])
    assert rc == 0
    assert (src / "photo.jpg").exists()


def test_run_and_undo_via_cli(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "photo.jpg").write_text("x")
    dest = tmp_path / "dest"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({
        "source": str(src),
        "rules": [{
            "name": "img", "match_any": [{"extension": [".jpg"]}],
            "action": {"type": "move", "target": str(dest)},
        }],
    }))
    manifest = tmp_path / "m.json"
    rc = main(["run", str(cfg), "--manifest", str(manifest), "--quiet"])
    assert rc == 0
    assert (dest / "photo.jpg").exists()
    assert manifest.is_file()

    rc2 = main(["undo", str(manifest), "--quiet"])
    assert rc2 == 0
    assert (src / "photo.jpg").exists()
    assert not (dest / "photo.jpg").exists()

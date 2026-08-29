"""Pruebas del motor de ejecución y reversión."""
from __future__ import annotations

import json
from pathlib import Path

from fileflow.config import Config
from fileflow.engine import Engine


def _config(source: Path, rules: list[dict]) -> Config:
    return Config(source=source, rules=rules)


def test_run_once_moves_file(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "photo.jpg").write_text("x")
    dest = tmp_path / "dest" / "img"
    engine = Engine(_config(src, [{
        "name": "img", "match_any": [{"extension": [".jpg"]}],
        "action": {"type": "move", "target": str(dest)},
    }]))
    result = engine.run_once()
    assert result.processed == 1
    assert (dest / "photo.jpg").exists()
    assert not (src / "photo.jpg").exists()


def test_dry_run_does_not_move(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "photo.jpg").write_text("x")
    dest = tmp_path / "dest"
    engine = Engine(_config(src, [{
        "name": "img", "match_any": [{"extension": [".jpg"]}],
        "action": {"type": "move", "target": str(dest)},
    }]), dry_run=True)
    result = engine.run_once()
    assert result.processed == 1
    assert (src / "photo.jpg").exists()
    assert not (dest / "photo.jpg").exists()


def test_rename_template(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "shot.png").write_text("x")
    dest = tmp_path / "dest"
    engine = Engine(_config(src, [{
        "name": "img", "match_any": [{"extension": [".png"]}],
        "action": {"type": "move", "target": str(dest), "rename": "{date}_{name}"},
    }]))
    engine.run_once()
    moved = list(dest.glob("*shot.png"))
    assert moved, "el archivo debe quedar renombrado con plantilla"


def test_copy_keeps_source(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "doc.pdf").write_text("x")
    dest = tmp_path / "dest"
    engine = Engine(_config(src, [{
        "name": "doc", "match_any": [{"extension": [".pdf"]}],
        "action": {"type": "copy", "target": str(dest)},
    }]))
    engine.run_once()
    assert (src / "doc.pdf").exists()
    assert (dest / "doc.pdf").exists()


def test_dedupe_on_collision(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("nuevo")
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a.txt").write_text("viejo")
    engine = Engine(_config(src, [{
        "name": "t", "match_any": [{"extension": [".txt"]}],
        "action": {"type": "move", "target": str(dest)},
    }]))
    engine.run_once()
    assert (dest / "a.txt").read_text() == "viejo"
    assert (dest / "a (1).txt").exists()


def test_target_date_templating(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "photo.jpg").write_text("x")
    # La carpeta destino usa marcadores de fecha que deben resolverse.
    engine = Engine(_config(src, [{
        "name": "img", "match_any": [{"extension": [".jpg"]}],
        "action": {"type": "move", "target": str(tmp_path / "out" / "{year}" / "{month}")},
    }]))
    engine.run_once()
    found = list((tmp_path / "out").rglob("photo.jpg"))
    assert found, "la ruta destino con {year}/{month} debe resolverse"
    # No debe quedar ninguna carpeta literal con llaves.
    assert not list((tmp_path / "out").glob("*{*"))


def test_manifest_and_undo(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "photo.jpg").write_text("x")
    dest = tmp_path / "dest"
    engine = Engine(_config(src, [{
        "name": "img", "match_any": [{"extension": [".jpg"]}],
        "action": {"type": "move", "target": str(dest)},
    }]))
    result = engine.run_once()
    manifest = engine.write_manifest(result, tmp_path / "manifest.json")
    data = json.loads(manifest.read_text())
    assert data["operations"][0]["action"] == "move"

    undo_result = Engine.undo(manifest)
    assert undo_result.processed == 1
    assert (src / "photo.jpg").exists()
    assert not (dest / "photo.jpg").exists()

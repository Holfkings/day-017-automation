"""Pruebas del motor de reglas."""
from __future__ import annotations

from pathlib import Path

from fileflow.rules import evaluate, first_matching_rule


def test_extension_match(tmp_path: Path):
    f = tmp_path / "img.jpg"
    f.write_text("x")
    rule = {"name": "img", "match": {"extension": [".jpg", ".png"]}, "action": {"type": "move"}}
    assert evaluate(rule, f).matched is True
    g = tmp_path / "doc.pdf"
    g.write_text("x")
    assert evaluate(rule, g).matched is False


def test_name_regex(tmp_path: Path):
    f = tmp_path / "factura-001.pdf"
    f.write_text("x")
    rule = {"name": "fac", "match": {"name_regex": "(?i)factura-.*\\.pdf$"}, "action": {}}
    assert evaluate(rule, f).matched is True


def test_mime_prefix(tmp_path: Path):
    f = tmp_path / "pic.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n")
    rule = {"name": "img", "match": {"mime_prefix": "image/"}, "action": {}}
    assert evaluate(rule, f).matched is True


def test_size(tmp_path: Path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"0" * 5000)
    rule = {"name": "big", "match": {"size": {"min": 1000, "max": 9999}}, "action": {}}
    assert evaluate(rule, f).matched is True


def test_age_days(tmp_path: Path):
    import os
    import time

    f = tmp_path / "old.txt"
    f.write_text("x")
    old = time.time() - 100 * 86400
    os.utime(f, (old, old))
    rule = {"name": "old", "match": {"age_days": {"min": 30}}, "action": {}}
    assert evaluate(rule, f).matched is True


def test_match_any_and_all(tmp_path: Path):
    f = tmp_path / "a.jpg"
    f.write_text("x")
    any_rule = {"name": "r", "match_any": [{"extension": [".jpg"]}, {"extension": [".png"]}], "action": {}}
    assert evaluate(any_rule, f).matched is True
    all_rule = {
        "name": "r",
        "match_all": [{"extension": [".jpg"]}, {"name_regex": "a\\.jpg$"}],
        "action": {},
    }
    assert evaluate(all_rule, f).matched is True
    all_rule_fail = {"name": "r", "match_all": [{"extension": [".jpg"]}, {"name_regex": "z\\.jpg$"}], "action": {}}
    assert evaluate(all_rule_fail, f).matched is False


def test_first_matching_rule(tmp_path: Path):
    f = tmp_path / "x.pdf"
    f.write_text("x")
    rules = [
        {"name": "img", "match": {"extension": [".jpg"]}, "action": {}},
        {"name": "doc", "match": {"extension": [".pdf"]}, "action": {}},
    ]
    assert first_matching_rule(rules, f)["name"] == "doc"
    jpg = tmp_path / "z.jpg"
    jpg.write_text("x")
    assert first_matching_rule(rules, jpg)["name"] == "img"

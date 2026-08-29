"""Definición y evaluación de criterios de coincidencia de reglas.

Una regla se compone de:
  * ``name``   — identificador legible (para logs).
  * ``match``  — criterio único que debe cumplirse.
  * ``match_all`` — lista de criterios que deben cumplirse TODOS.
  * ``match_any`` — lista de criterios de los cuales basta UNO.
  * ``action`` — qué hacer con el archivo coincidente.

Criterios soportados (todos opcionales, se combinan con AND):
  * ``extension``: lista de extensiones (sin distinción de mayúsculas).
  * ``name_regex``: expresión regular sobre el nombre (sin ruta).
  * ``mime_prefix``: prefijo del tipo MIME deducido (p. ej. ``image/``).
  * ``size``: ``{"min": bytes, "max": bytes}`` (límites inclusivos).
  * ``age_days``: ``{"min": días, "max": días}`` (edad del archivo).
"""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RuleMatch:
    """Resultado de evaluar un archivo contra una regla."""

    matched: bool
    rule_name: str
    reason: str = ""


def _norm_ext(ext: str) -> str:
    return ext.lower() if ext.startswith(".") else "." + ext.lower()


def _matches_criterion(path: Path, stat: Any, crit: dict[str, Any]) -> bool:
    if "extension" in crit:
        wanted = {_norm_ext(e) for e in crit["extension"]}
        if path.suffix.lower() not in wanted:
            return False

    if "name_regex" in crit:
        pattern = re.compile(crit["name_regex"])
        if not pattern.search(path.name):
            return False

    if "mime_prefix" in crit:
        mime, _ = mimetypes.guess_type(str(path))
        if not mime or not mime.startswith(crit["mime_prefix"]):
            return False

    if "size" in crit:
        size_cfg = crit["size"]
        if "min" in size_cfg and stat.st_size < size_cfg["min"]:
            return False
        if "max" in size_cfg and stat.st_size > size_cfg["max"]:
            return False

    if "age_days" in crit:
        import time

        age = (time.time() - stat.st_mtime) / 86400.0
        age_cfg = crit["age_days"]
        if "min" in age_cfg and age < age_cfg["min"]:
            return False
        if "max" in age_cfg and age > age_cfg["max"]:
            return False

    return True


def _criteria_for(rule: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Devuelve (criterios, modo_any). Por defecto un único ``match`` (AND)."""
    if "match_any" in rule:
        return list(rule["match_any"]), True
    if "match_all" in rule:
        return list(rule["match_all"]), False
    return [rule["match"]], False


def evaluate(rule: dict[str, Any], path: Path) -> RuleMatch:
    """Evalúa un archivo contra una regla."""
    name = str(rule.get("name", "<sin nombre>"))
    try:
        stat = path.stat()
    except OSError as exc:
        return RuleMatch(False, name, f"no accesible: {exc}")

    criteria, any_mode = _criteria_for(rule)
    if not criteria:
        return RuleMatch(False, name, "sin criterios")

    results = [_matches_criterion(path, stat, c) for c in criteria]
    ok = any(results) if any_mode else all(results)
    if ok:
        return RuleMatch(True, name)
    return RuleMatch(False, name, "criterios no cumplidos")


def first_matching_rule(rules: list[dict[str, Any]], path: Path) -> dict[str, Any] | None:
    """Devuelve la primera regla que coincide (o ``None``)."""
    for rule in rules:
        if evaluate(rule, path).matched:
            return rule
    return None

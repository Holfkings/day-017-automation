"""Carga y validación de la configuración de FileFlow.

El formato es JSON (sin dependencias externas). Si ``pyyaml`` está
disponible, también se acepta YAML. La configuración define una carpeta
de origen y una lista ordenada de reglas; se evalúa la primera regla
cuyo criterio de coincidencia sea verdadero (comportamiento tipo
cortafuegos).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # pragma: no cover - dependencia opcional
    import yaml  # type: ignore

    _HAS_YAML = True
except Exception:  # pragma: no cover
    _HAS_YAML = False


class ConfigError(ValueError):
    """La configuración es inválida o está incompleta."""


@dataclass
class Config:
    """Configuración validada de una automatización."""

    source: Path
    rules: list[dict[str, Any]] = field(default_factory=list)
    recursive: bool = False
    description: str = ""
    version: int = 1

    @property
    def source_str(self) -> str:
        return str(self.source)


def _expand(path: str) -> Path:
    """Expande ``~`` y variables de entorno y devuelve una ruta absoluta."""
    expanded = os.path.expanduser(os.path.expandvars(path))
    return Path(expanded).resolve()


def _coerce_rules(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ConfigError("'rules' debe ser una lista de reglas.")
    cleaned: list[dict[str, Any]] = []
    for i, rule in enumerate(raw):
        if not isinstance(rule, dict):
            raise ConfigError(f"La regla #{i + 1} no es un objeto.")
        if "action" not in rule:
            raise ConfigError(f"La regla #{i + 1} carece de 'action'.")
        if "match" not in rule and "match_all" not in rule and "match_any" not in rule:
            raise ConfigError(
                f"La regla #{i + 1} debe definir 'match', 'match_any' o 'match_all'."
            )
        cleaned.append(rule)
    return cleaned


def load_config(path: str | os.PathLike[str]) -> Config:
    """Carga y valida un archivo de configuración (JSON o YAML)."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"No existe el archivo de configuración: {p}")

    text = p.read_text(encoding="utf-8")
    try:
        if p.suffix.lower() in (".yaml", ".yml"):
            if not _HAS_YAML:
                raise ConfigError(
                    "Se requiere 'pyyaml' para leer YAML; usa JSON o instala pyyaml."
                )
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    except Exception as exc:  # pragma: no cover - errores de parseo
        raise ConfigError(f"No se pudo interpretar la configuración: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("La configuración raíz debe ser un objeto.")

    source_raw = data.get("source")
    if not source_raw:
        raise ConfigError("Falta 'source' (carpeta de origen).")
    source = _expand(str(source_raw))
    if not source.is_dir():
        raise ConfigError(f"La carpeta de origen no existe: {source}")

    return Config(
        source=source,
        rules=_coerce_rules(data.get("rules", [])),
        recursive=bool(data.get("recursive", False)),
        description=str(data.get("description", "")),
        version=int(data.get("version", 1)),
    )


def dump_sample(dest: str | os.PathLike[str], name: str = "Mi automatización") -> Path:
    """Escribe una configuración de ejemplo lista para adaptar."""
    dest = Path(dest)
    sample = {
        "version": 1,
        "description": name,
        "source": "~/Downloads",
        "recursive": False,
        "rules": [
            {
                "name": "Imágenes a Fotos",
                "match_any": [
                    {"extension": [".jpg", ".jpeg", ".png", ".gif", ".webp"]}
                ],
                "action": {
                    "type": "move",
                    "target": "~/Downloads/Organizado/Imágenes/{year}/{month}",
                    "rename": "{date}_{name}",
                },
            },
            {
                "name": "Documentos a Documentos",
                "match_any": [
                    {"extension": [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".csv"]}
                ],
                "action": {
                    "type": "move",
                    "target": "~/Downloads/Organizado/Documentos",
                },
            },
        ],
    }
    dest.write_text(
        json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return dest

"""Motor de ejecución: aplica reglas a archivos y registra auditoría.

El motor recorre la carpeta de origen, encuentra la primera regla que
coincide con cada archivo y ejecuta su acción. Todas las operaciones
quedan registradas en un manifiesto JSON que permite revertirlas.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import Config, ConfigError, load_config
from .rules import evaluate, first_matching_rule


MANIFEST_VERSION = 1


@dataclass
class Operation:
    """Una acción ejecutada sobre un archivo (para auditoría/reversión)."""

    action: str
    source: str
    destination: str | None
    rule: str
    timestamp: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "source": self.source,
            "destination": self.destination,
            "rule": self.rule,
            "timestamp": self.timestamp,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Operation":
        return cls(
            action=d["action"],
            source=d["source"],
            destination=d.get("destination"),
            rule=d.get("rule", ""),  # type: ignore[arg-type]
            timestamp=d.get("timestamp", ""),
            error=d.get("error"),
        )


@dataclass
class RunResult:
    """Resumen de una ejecución del motor."""

    scanned: int = 0
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    operations: list[Operation] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "processed": self.processed,
            "skipped": self.skipped,
            "errors": self.errors,
            "dry_run": self.dry_run,
            "operations": [op.to_dict() for op in self.operations],
        }


def _render_template(template: str, path: Path, now: _dt.datetime) -> str:
    """Sustituye marcadores en una plantilla de nombre/ruta."""
    stem = path.stem
    suffix = path.suffix
    return (
        template.replace("{year}", f"{now.year:04d}")
        .replace("{month}", f"{now.month:02d}")
        .replace("{day}", f"{now.day:02d}")
        .replace("{date}", now.strftime("%Y-%m-%d"))
        .replace("{timestamp}", now.strftime("%Y%m%d-%H%M%S"))
        .replace("{name}", stem)
        .replace("{ext}", suffix)
    )


def _preserve_ext(rendered: str, path: Path) -> str:
    """Conserva la extensión original salvo que la plantilla la incluya."""
    if path.suffix and not rendered.endswith(path.suffix):
        return rendered + path.suffix
    return rendered


def _expand_dest(dest: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(dest))).resolve()


class Engine:
    """Aplica reglas a archivos de una carpeta de origen."""

    def __init__(
        self,
        config: Config,
        dry_run: bool = False,
        on_event: Callable[[Operation], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.dry_run = dry_run
        self._on_event = on_event
        self._on_log = on_log

    # -- API de alto nivel -------------------------------------------------

    @classmethod
    def from_config_file(
        cls, path: str | os.PathLike[str], dry_run: bool = False, **kw: Any
    ) -> "Engine":
        return cls(load_config(path), dry_run=dry_run, **kw)

    def run_once(self) -> RunResult:
        """Aplica reglas a los archivos actuales del origen (una pasada)."""
        result = RunResult(dry_run=self.dry_run)
        source = self.config.source
        files = (
            (f for f in source.rglob("*") if f.is_file())
            if self.config.recursive
            else (f for f in source.iterdir() if f.is_file())
        )
        for path in files:
            result.scanned += 1
            rule = first_matching_rule(self.config.rules, path)
            if rule is None:
                result.skipped += 1
                continue
            op = self._apply(path, rule)
            result.operations.append(op)
            if op.error:
                result.errors += 1
            else:
                result.processed += 1
            if self._on_event:
                self._on_event(op)
        if self._on_log:
            self._on_log(
                f"Pasada completa: {result.processed} procesados, "
                f"{result.skipped} omitidos, {result.errors} errores "
                f"(dry_run={self.dry_run})."
            )
        return result

    # -- Núcleo de acciones ------------------------------------------------

    def _apply(self, path: Path, rule: dict[str, Any]) -> Operation:
        action = rule.get("action", {})
        atype = action.get("type", "move").lower()
        rule_name = str(rule.get("name", "<sin nombre>"))
        now = _dt.datetime.now()
        ts = now.isoformat(timespec="seconds")

        if atype == "run":
            return self._do_run(path, action, rule_name, ts)
        if atype in ("move", "copy", "rename"):
            return self._do_fs(path, action, atype, rule_name, ts)
        return Operation(
            action=atype,
            source=str(path),
            destination=None,
            rule=rule_name,
            timestamp=ts,
            error=f"acción desconocida: {atype}",
        )

    def _do_fs(
        self, path: Path, action: dict[str, Any], atype: str, rule_name: str, ts: str
    ) -> Operation:
        rename_tpl = action.get("rename")
        if atype == "rename":
            new_name = (
                _preserve_ext(_render_template(rename_tpl, path, _dt.datetime.now()), path)
                if rename_tpl
                else path.name
            )
            dest = path.parent / new_name
        else:
            target = action.get("target")
            if not target:
                return Operation(
                    atype, str(path), None, rule_name, ts,
                    error="falta 'target' en la acción",
                )
            base = _expand_dest(_render_template(target, path, _dt.datetime.now()))
            if rename_tpl:
                base = base / _preserve_ext(
                    _render_template(rename_tpl, path, _dt.datetime.now()), path
                )
            else:
                base = base / path.name
            dest = base

        if dest.exists():
            dest = self._dedupe(dest)
        if self.dry_run:
            return Operation(atype, str(path), str(dest), rule_name, ts)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if atype == "move":
                shutil.move(str(path), str(dest))
            elif atype == "copy":
                shutil.copy2(str(path), str(dest))
            return Operation(atype, str(path), str(dest), rule_name, ts)
        except OSError as exc:
            return Operation(atype, str(path), str(dest), rule_name, ts, error=str(exc))

    def _do_run(
        self, path: Path, action: dict[str, Any], rule_name: str, ts: str
    ) -> Operation:
        cmd_tpl = action.get("command")
        if not cmd_tpl:
            return Operation(
                "run", str(path), None, rule_name, ts,
                error="falta 'command' en la acción run",
            )
        cmd = _render_template(cmd_tpl, path, _dt.datetime.now())
        # Sustituir también {path} por la ruta real del archivo.
        cmd = cmd.replace("{path}", str(path))
        if self.dry_run:
            return Operation("run", str(path), cmd, rule_name, ts)
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )
            if proc.returncode != 0:
                return Operation(
                    "run", str(path), cmd, rule_name, ts,
                    error=f"código {proc.returncode}: {proc.stderr[:300]}",
                )
            return Operation("run", str(path), cmd, rule_name, ts)
        except Exception as exc:  # pragma: no cover - dependiente del SO
            return Operation("run", str(path), cmd, rule_name, ts, error=str(exc))

    @staticmethod
    def _dedupe(dest: Path) -> Path:
        if not dest.exists():
            return dest
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        i = 1
        while True:
            candidate = parent / f"{stem} ({i}){suffix}"
            if not candidate.exists():
                return candidate
            i += 1

    # -- Manifiesto / reversión -------------------------------------------

    def write_manifest(self, result: RunResult, path: str | os.PathLike[str]) -> Path:
        data = {
            "version": MANIFEST_VERSION,
            "dry_run": result.dry_run,
            "generated": _dt.datetime.now().isoformat(timespec="seconds"),
            "operations": [op.to_dict() for op in result.operations if not op.error],
        }
        p = Path(path)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return p

    @classmethod
    def undo(cls, manifest_path: str | os.PathLike[str]) -> RunResult:
        """Revierte las operaciones registradas en un manifiesto."""
        p = Path(manifest_path)
        if not p.is_file():
            raise ConfigError(f"Manifiesto no encontrado: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
        result = RunResult()
        for op in data.get("operations", []):
            obj = Operation.from_dict(op)
            result.scanned += 1
            ts = _dt.datetime.now().isoformat(timespec="seconds")
            try:
                if obj.action == "move":
                    shutil.move(obj.destination, obj.source)
                elif obj.action == "copy":
                    Path(obj.destination).unlink(missing_ok=True)
                elif obj.action == "rename":
                    Path(obj.destination).rename(Path(obj.source))
                elif obj.action == "run":
                    continue  # las acciones externas no se revierten
                result.processed += 1
                result.operations.append(
                    Operation("undo:" + obj.action, obj.destination, obj.source, obj.rule, ts)
                )
            except OSError as exc:
                result.errors += 1
                result.operations.append(
                    Operation("undo:" + obj.action, obj.destination, obj.source,
                              obj.rule, ts, error=str(exc))
                )
        return result

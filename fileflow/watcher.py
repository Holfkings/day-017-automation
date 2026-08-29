"""Modo vigilancia: aplica reglas a archivos nuevos o ya estables.

En lugar de depender de bibliotecas nativas de cada sistema, FileFlow
sondea la carpeta de origen. Para evitar actuar sobre archivos que aún
se están escribiendo, un archivo solo se procesa cuando su tamaño y
fecha de modificación no cambian durante ``stable_seconds``.
"""

from __future__ import annotations

import time
from pathlib import Path

from .engine import Engine, RunResult
from .rules import first_matching_rule


class Watcher:
    """Vigila una carpeta y ejecuta el motor al detectar archivos estables."""

    def __init__(
        self,
        engine: Engine,
        interval: float = 15.0,
        stable_seconds: float = 2.0,
    ) -> None:
        self.engine = engine
        self.interval = interval
        self.stable_seconds = stable_seconds
        self._seen: dict[Path, tuple[float, float]] = {}

    def _is_stable(self, path: Path) -> bool:
        try:
            st = path.stat()
        except OSError:
            return False
        key = (st.st_size, st.st_mtime)
        previous = self._seen.get(path)
        if previous != key:
            self._seen[path] = key
            return False
        return True

    def _candidates(self) -> list[Path]:
        source = self.engine.config.source
        files = (
            [f for f in source.rglob("*") if f.is_file()]
            if self.engine.config.recursive
            else [f for f in source.iterdir() if f.is_file()]
        )
        return [f for f in files if self._is_stable(f)]

    def tick(self) -> RunResult:
        """Una pasada: procesa los archivos estables que coincidan."""
        result = RunResult(dry_run=self.engine.dry_run)
        for path in self._candidates():
            rule = first_matching_rule(self.engine.config.rules, path)
            if rule is None:
                continue
            op = self.engine._apply(path, rule)  # noqa: SLF001 (helper interno)
            result.operations.append(op)
            if op.error:
                result.errors += 1
            else:
                result.processed += 1
            result.scanned += 1
        return result

    def run_forever(self, stop: callable[[], bool] | None = None) -> None:
        """Bucle de vigilancia hasta interrupción o ``stop()`` verdadero."""
        while True:
            try:
                self.tick()
            except Exception:  # pragma: no cover - robustez del bucle
                pass
            if stop is not None and stop():
                break
            time.sleep(self.interval)

"""FileFlow — motor de automatización de archivos por reglas.

FileFlow vigila carpetas y aplica reglas declarativas a los archivos que
aparecen o cambian: mover, copiar, renombrar o disparar comandos, con
plantillas de destino, modo simulación (dry-run), registro de auditoría
y reversión automática de la última ejecución.

Dependencias: solo la biblioteca estándar de Python (>=3.8).
"""

from __future__ import annotations

__version__ = "1.0.0"

from .config import ConfigError, load_config
from .rules import RuleMatch
from .engine import Engine, Operation, RunResult

__all__ = [
    "ConfigError",
    "load_config",
    "Rule",
    "RuleMatch",
    "Engine",
    "Operation",
    "RunResult",
    "__version__",
]

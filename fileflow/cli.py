"""Interfaz de línea de comandos de FileFlow.

Comandos:
  run     Aplica las reglas a los archivos actuales (una pasada).
  watch   Vigila la carpeta y actúa sobre archivos nuevos/estables.
  undo    Revierte la última ejecución usando su manifiesto.
  init    Crea una configuración de ejemplo.
  version Muestra la versión.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, dump_sample
from .engine import Engine
from .watcher import Watcher


def _print_result(result, quiet: bool) -> None:
    if quiet:
        return
    tag = "[simulación] " if result.dry_run else ""
    print(
        f"{tag}Escaneados: {result.scanned} · "
        f"Procesados: {result.processed} · "
        f"Omitidos: {result.skipped} · Errores: {result.errors}"
    )
    if not quiet:
        for op in result.operations:
            mark = "✗" if op.error else "→"
            dest = op.destination or ""
            print(f"  {mark} {op.action}: {Path(op.source).name} -> {dest}")
            if op.error:
                print(f"      error: {op.error}")


def cmd_run(args: argparse.Namespace) -> int:
    engine = Engine.from_config_file(
        args.config, dry_run=args.dry_run,
        on_log=lambda m: print(m, file=sys.stderr) if not args.quiet else None,
    )
    result = engine.run_once()
    if args.manifest and not args.dry_run:
        p = engine.write_manifest(result, args.manifest)
        print(f"Manifiesto: {p}", file=sys.stderr)
    _print_result(result, args.quiet)
    return 1 if result.errors and not args.dry_run else 0


def cmd_watch(args: argparse.Namespace) -> int:
    engine = Engine.from_config_file(args.config, dry_run=args.dry_run)
    watcher = Watcher(engine, interval=args.interval, stable_seconds=args.stable)
    print(
        f"Vigilando {engine.config.source} cada {args.interval}s "
        f"(Ctrl+C para detener)…",
        file=sys.stderr,
    )
    try:
        watcher.run_forever()
    except KeyboardInterrupt:  # pragma: no cover - interacción manual
        print("\nDetenido.", file=sys.stderr)
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    try:
        result = Engine.undo(args.manifest)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    _print_result(result, args.quiet)
    return 1 if result.errors else 0


def cmd_init(args: argparse.Namespace) -> int:
    dest = Path(args.output)
    if dest.exists() and not args.force:
        print(f"Ya existe {dest}. Usa --force para sobrescribir.", file=sys.stderr)
        return 1
    p = dump_sample(dest, name=args.name)
    print(f"Configuración de ejemplo creada: {p}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fileflow",
        description="Motor de automatización de archivos por reglas.",
    )
    parser.add_argument(
        "--version", action="version", version=f"fileflow {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="aplica reglas una vez")
    p_run.add_argument("config", help="ruta del archivo de configuración")
    p_run.add_argument("--dry-run", action="store_true", help="no ejecuta, solo muestra")
    p_run.add_argument("--manifest", help="guarda manifiesto de auditoría aquí")
    p_run.add_argument("--quiet", action="store_true", help="solo código de salida")
    p_run.set_defaults(func=cmd_run)

    p_watch = sub.add_parser("watch", help="vigila y actúa sobre archivos nuevos")
    p_watch.add_argument("config")
    p_watch.add_argument("--interval", type=float, default=15.0, help="segundos entre sondeos")
    p_watch.add_argument("--stable", type=float, default=2.0, help="segundos de estabilidad")
    p_watch.add_argument("--dry-run", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    p_undo = sub.add_parser("undo", help="revierte una ejecución por su manifiesto")
    p_undo.add_argument("manifest")
    p_undo.add_argument("--quiet", action="store_true")
    p_undo.set_defaults(func=cmd_undo)

    p_init = sub.add_parser("init", help="crea una configuración de ejemplo")
    p_init.add_argument("--output", default="fileflow.json")
    p_init.add_argument("--name", default="Mi automatización")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Archivo no encontrado: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

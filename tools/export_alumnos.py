#!/usr/bin/env python3
"""Arma dist/alumnos/ con lo que se reparte a los alumnos (sin soluciones ni guías).

Uso: python tools/export_alumnos.py [M2-reflection ...]   (sin args: todos los módulos)
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "alumnos"
EXCLUIR_NOMBRES = {"notebook_solucion.ipynb", "guia_docente.md", "lab.py", "__pycache__", ".pytest_cache"}
EXCLUIR_SUFIJOS = {".pyc"}


def copiar_modulo(mod: Path) -> int:
    n = 0
    for src in mod.rglob("*"):
        if any(part in EXCLUIR_NOMBRES for part in src.relative_to(ROOT).parts):
            continue
        if src.suffix in EXCLUIR_SUFIJOS or src.is_dir():
            continue
        dst = DIST / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def main() -> int:
    mods = [ROOT / m for m in sys.argv[1:]] or sorted(p for p in ROOT.glob("M*-*") if p.is_dir())
    if DIST.exists():
        shutil.rmtree(DIST)
    total = 0
    for mod in mods:
        total += copiar_modulo(mod)
    for extra in ("requirements.txt", ".env.example", "README.md", "pytest.ini", "CONVENCIONES.md"):
        if (ROOT / extra).exists():
            shutil.copy2(ROOT / extra, DIST / extra)
    (DIST / "setup").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "setup" / "check_env.py", DIST / "setup" / "check_env.py")
    print(f"{total} archivos copiados a {DIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

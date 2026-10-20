#!/usr/bin/env python3
"""Corre los tests de cada lab en su propia carpeta (evita choques entre los `utils.py`).

Uso: python tools/run_tests.py            # todos
     python tools/run_tests.py M3-tool-use # un módulo
Los tests que requieren API se saltan solos si no hay OPENAI_API_KEY.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def carpetas_con_tests(base: Path):
    vistos = set()
    for p in sorted(base.rglob("test*.py")):
        if any(part.startswith((".", "dist", "__pycache__")) for part in p.relative_to(ROOT).parts):
            continue
        d = p.parent
        if d.name == "tests":  # p. ej. email_server/tests/test_api.py → correr desde email_server/
            d = d.parent
        if d not in vistos:
            vistos.add(d)
            yield d


def main() -> int:
    bases = [ROOT / a for a in sys.argv[1:]] or [ROOT]
    fallas = 0
    for base in bases:
        for d in carpetas_con_tests(base):
            print(f"\n=== {d.relative_to(ROOT)} ===")
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=d)
            fallas += r.returncode not in (0, 5)  # 5 = no se recolectaron tests
    print("\nTodo verde." if not fallas else f"\n{fallas} carpeta(s) con fallas.")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())

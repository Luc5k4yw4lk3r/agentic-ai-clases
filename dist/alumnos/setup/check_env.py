#!/usr/bin/env python3
"""Verifica que el entorno esté listo para los labs. Correr: python setup/check_env.py

No llama a ninguna API paga salvo que pases --llamar (hace una llamada mínima a OpenAI).
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

OK, FAIL, WARN = "OK   ", "FALTA", "AVISO"
ROOT = Path(__file__).resolve().parent.parent

PAQUETES = {
    "aisuite": "aisuite[openai]",
    "openai": "openai",
    "dotenv": "python-dotenv",
    "pandas": "pandas",
    "tabulate": "tabulate",
    "duckdb": "duckdb",
    "tinydb": "tinydb",
    "matplotlib": "matplotlib",
    "tavily": "tavily-python",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "sqlalchemy": "sqlalchemy",
    "jupytext": "jupytext",
    "nbformat": "nbformat",
}


def main() -> int:
    problemas = 0
    print(f"Python {sys.version.split()[0]}", end="  ")
    if sys.version_info < (3, 11):
        print(f"{FAIL} se necesita 3.11+")
        problemas += 1
    else:
        print(OK)

    for mod, pip_name in PAQUETES.items():
        try:
            importlib.import_module(mod)
            print(f"{OK} {pip_name}")
        except ImportError:
            print(f"{FAIL} {pip_name}  →  pip install {pip_name}")
            problemas += 1

    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"{FAIL} no existe {env_path}  →  cp .env.example .env")
        return 1
    from dotenv import load_dotenv

    load_dotenv(env_path)
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key.startswith("sk-..."):
        print(f"{FAIL} OPENAI_API_KEY sin completar en .env")
        problemas += 1
    else:
        print(f"{OK} OPENAI_API_KEY ({key[:7]}…)")
    tav = os.getenv("TAVILY_API_KEY", "")
    if not tav or tav.startswith("tvly-..."):
        print(f"{WARN} TAVILY_API_KEY sin completar: los labs de búsqueda web usan el fallback")
    else:
        print(f"{OK} TAVILY_API_KEY ({tav[:7]}…)")
    cheap = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")
    strong = os.getenv("MODEL_STRONG", "gpt-4.1")
    print(f"{OK} MODEL_CHEAP={cheap}  MODEL_STRONG={strong}")
    for m in (cheap, strong):
        if m.startswith(("o4", "o3", "o1", "gpt-4o")) or ":" in m:
            print(f"{WARN} {m}: modelo retirado o con prefijo de proveedor; usá un nombre sin 'openai:' (ver README)")

    if "--llamar" in sys.argv and not problemas:
        import aisuite as ai

        client = ai.Client()
        r = client.chat.completions.create(
            model=f"openai:{cheap}", messages=[{"role": "user", "content": "Respondé solo: listo"}]
        )
        print(f"{OK} llamada de prueba a openai:{cheap} → {r.choices[0].message.content!r}")

    print("\nTodo listo." if not problemas else f"\n{problemas} problema(s). Resolvelos y volvé a correr.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())

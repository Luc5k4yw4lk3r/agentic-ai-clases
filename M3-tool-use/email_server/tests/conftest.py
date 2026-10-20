"""Configuración de pytest: base temporal y ruta de import.

Se ejecuta antes que los tests. Apunta la DB a un archivo temporal (para no
pisar la casilla que usan los notebooks) y agrega `M3-tool-use/` al path para
que `import email_server` funcione se corra pytest desde donde se corra.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="emails_test_")
os.environ["M3_EMAIL_DB_PATH"] = str(Path(_TMP) / "emails_test.db")

M3_DIR = Path(__file__).resolve().parents[2]  # .../M3-tool-use
if str(M3_DIR) not in sys.path:
    sys.path.insert(0, str(M3_DIR))

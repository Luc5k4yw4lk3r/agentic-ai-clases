"""Conexión a la base SQLite y fábrica de sesiones de SQLAlchemy.

Es el mismo patrón que usaron en TaskFlow: un `engine`, una fábrica
`SessionLocal` y una dependencia `get_db()` que FastAPI inyecta en cada endpoint
y que cierra la sesión al terminar la request.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# La base vive al lado de este archivo, sin importar desde qué carpeta se levante
# uvicorn. Los tests la redirigen a un archivo temporal con M3_EMAIL_DB_PATH.
DB_PATH = Path(os.getenv("M3_EMAIL_DB_PATH", str(Path(__file__).with_name("emails.db"))))

# check_same_thread=False: SQLite por defecto no deja compartir la conexión entre
# hilos, y FastAPI atiende cada request en un hilo distinto.
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Clase base de la que heredan los modelos (tablas)."""


def get_db():
    """Dependencia de FastAPI: abre una sesión por request y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

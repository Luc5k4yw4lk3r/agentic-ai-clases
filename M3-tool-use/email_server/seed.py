"""Datos semilla: la casilla con la que arranca (y a la que vuelve) el servidor.

Seis mails coherentes entre sí. Tu dirección es siempre `vos@empresa.com`
(el material original mezclaba `you@email.com` y `you@mail.com`, lo que hacía
que los filtros por destinatario fallaran a veces).

Las fechas son relativas al momento en que se carga la semilla, así los pedidos
tipo "los mails de esta semana" tienen sentido cualquier día que se dicte la
clase.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import Email

MI_EMAIL = "vos@empresa.com"


def _hace(ahora: datetime, dias: int, horas: int = 0) -> datetime:
    """Devuelve una fecha `dias` días y `horas` horas antes de `ahora`."""
    return ahora - timedelta(days=dias, hours=horas)


def emails_semilla(ahora: datetime | None = None) -> list[dict]:
    """Lista de dicts con los 6 mails iniciales (ids fijos del 1 al 6)."""
    if ahora is None:
        ahora = datetime.now()
    return [
        {
            "id": 1,
            "remitente": "novedades@newsletter-tech.com",
            "destinatario": MI_EMAIL,
            "asunto": "Newsletter semanal: lo nuevo en agentes de IA",
            "cuerpo": (
                "Esta semana: function calling en producción, qué es MCP y por qué "
                "todos hablan de él, y tres repos para probar el fin de semana."
            ),
            "fecha": _hace(ahora, 4, 3),
            "leido": True,
        },
        {
            "id": 2,
            "remitente": MI_EMAIL,
            "destinatario": "jefa@empresa.com",
            "asunto": "Días libres",
            "cuerpo": "Hola Marina, ¿puedo tomarme el lunes y el martes de la semana que viene? Saludos.",
            "fecha": _hace(ahora, 4, 1),
            "leido": True,
        },
        {
            "id": 3,
            "remitente": "jefa@empresa.com",
            "destinatario": MI_EMAIL,
            "asunto": "Reporte trimestral",
            "cuerpo": (
                "Hola, ¿me pasás el reporte del Q3 antes del jueves? Necesito los números "
                "de ventas y el resumen de incidentes. Gracias. Marina"
            ),
            "fecha": _hace(ahora, 3, 2),
            "leido": False,
        },
        {
            "id": 4,
            "remitente": "sofia@empresa.com",
            "destinatario": MI_EMAIL,
            "asunto": "Duda sobre el endpoint de tareas",
            "cuerpo": (
                "¿El PATCH /tareas/{id} acepta cambiar solo el estado o hay que mandar "
                "todo el objeto? Me devuelve 422 y no entiendo por qué."
            ),
            "fecha": _hace(ahora, 2, 5),
            "leido": False,
        },
        {
            "id": 5,
            "remitente": "rrhh@empresa.com",
            "destinatario": MI_EMAIL,
            "asunto": "After del viernes",
            "cuerpo": "Este viernes a las 18 hacemos un after en la terraza. Confirmá asistencia respondiendo este mail.",
            "fecha": _hace(ahora, 1, 4),
            "leido": False,
        },
        {
            "id": 6,
            "remitente": "tomas@empresa.com",
            "destinatario": MI_EMAIL,
            "asunto": "Review del PR #42",
            "cuerpo": (
                "Te dejé comentarios en el PR del módulo de autenticación. Hay dos cosas "
                "que conviene arreglar antes del merge."
            ),
            "fecha": _hace(ahora, 0, 2),
            "leido": False,
        },
    ]


def cargar_semilla(db: Session) -> int:
    """Borra todo y vuelve a cargar los 6 mails. Devuelve cuántos cargó."""
    db.query(Email).delete()
    datos = emails_semilla()
    for fila in datos:
        db.add(Email(**fila))
    db.commit()
    return len(datos)

"""Schemas de Pydantic: qué entra y qué sale por la API.

Separar el schema (lo que viaja por HTTP) del modelo (lo que se guarda en la
tabla) es la misma idea que vieron en TaskFlow: el cliente nunca manda el `id`
ni la `fecha`, los pone el servidor.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmailNuevo(BaseModel):
    """Cuerpo del POST /send. El remitente lo pone el servidor."""

    destinatario: str = Field(..., min_length=3, examples=["jefa@empresa.com"])
    asunto: str = Field(..., min_length=1, examples=["Reporte Q3"])
    cuerpo: str = Field(..., min_length=1, examples=["Te paso el reporte adjunto."])


class EmailOut(BaseModel):
    """Un email tal como lo devuelve la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    remitente: str
    destinatario: str
    asunto: str
    cuerpo: str
    fecha: datetime
    leido: bool


class Mensaje(BaseModel):
    """Confirmación de un borrado."""

    mensaje: str
    id: int


class ResetOut(BaseModel):
    """Confirmación del reset: cuántos mails quedaron cargados."""

    mensaje: str
    cantidad: int

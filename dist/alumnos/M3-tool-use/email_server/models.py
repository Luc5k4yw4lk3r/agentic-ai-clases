"""Modelo ORM: la tabla `emails`.

Una sola tabla alcanza para simular una casilla: guarda tanto los mails que
recibís como los que mandás (se distinguen por `remitente` / `destinatario`).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    remitente: Mapped[str] = mapped_column(String, nullable=False)
    destinatario: Mapped[str] = mapped_column(String, nullable=False)
    asunto: Mapped[str] = mapped_column(String, nullable=False)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    leido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

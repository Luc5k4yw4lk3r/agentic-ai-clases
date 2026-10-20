"""Tools del asistente de email: una función Python por endpoint del servidor.

Cada función envuelve una ruta HTTP del servidor simulado (`email_server/`) y
devuelve el JSON ya parseado (dicts y listas), que es lo que el modelo va a
leer.

Los docstrings están en español y son MUY importantes: `aisuite` los lee para
armar el schema de cada tool, y ese schema es la única documentación que ve el
modelo para decidir qué tool llamar y con qué argumentos. Si un docstring es
vago, el agente se equivoca.

Dos tools faltan a propósito (las escribís vos en el notebook):
    - marcar_como_leido(email_id)
    - buscar_no_leidos_de(remitente)
"""
from __future__ import annotations

import os

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

BASE_URL = os.getenv("M3_EMAIL_SERVER_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 10


def _pedir(metodo: str, ruta: str, **kwargs):
    """Hace la request al servidor y devuelve el JSON. Errores legibles en español.

    - Si el servidor no responde: levanta ConnectionError con la explicación (no
      tiene sentido que el agente siga intentando).
    - Si el servidor responde 4xx/5xx: devuelve {"error": ..., "status": ...}
      para que el modelo lo lea y decida qué hacer.
    """
    url = f"{BASE_URL}{ruta}"
    try:
        resp = requests.request(metodo, url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"No pude conectarme al servidor de email en {BASE_URL}. "
            "¿Está levantado? Desde la carpeta M3-tool-use/ corré: "
            "uvicorn email_server.main:app --reload --port 8000"
        ) from None
    if resp.status_code >= 400:
        try:
            detalle = resp.json().get("detail", resp.text)
        except ValueError:
            detalle = resp.text
        return {"error": detalle, "status": resp.status_code}
    return resp.json()


def listar_todos() -> list[dict]:
    """Devuelve todos los emails de la casilla, del más nuevo al más viejo.

    Incluye leídos y no leídos. Cada email es un dict con las claves id,
    remitente, destinatario, asunto, cuerpo, fecha (texto ISO) y leido (bool).

    Returns:
        Lista de dicts, uno por email.
    """
    return _pedir("GET", "/emails")


def listar_no_leidos() -> list[dict]:
    """Devuelve solo los emails no leídos, del más nuevo al más viejo.

    Misma estructura que listar_todos. Usala cuando el pedido hable de mails
    "nuevos", "pendientes" o "sin leer".

    Returns:
        Lista de dicts; vacía si no hay no leídos.
    """
    return _pedir("GET", "/emails/unread")


def buscar_emails(texto: str) -> list[dict]:
    """Busca emails que contengan el texto en el asunto, el cuerpo o el remitente.

    No distingue mayúsculas. Usala para encontrar un mail por tema ("after",
    "reporte") o por remitente ("jefa@empresa.com").

    Args:
        texto: palabra o frase a buscar. Ej: "reporte".

    Returns:
        Lista de dicts con los emails que coinciden; vacía si no hay ninguno.
    """
    return _pedir("GET", "/emails/search", params={"q": texto})


def filtrar_emails(destinatario: str | None = None, desde: str | None = None, hasta: str | None = None) -> list[dict]:
    """Filtra emails por destinatario y/o por rango de fechas.

    Todos los argumentos son opcionales y se combinan. Para "los mails que mandé
    a X" usá destinatario; para "los mails de esta semana" usá desde/hasta.

    Args:
        destinatario: dirección exacta del destinatario. Ej: "jefa@empresa.com".
        desde: fecha inicial en formato YYYY-MM-DD (inclusive).
        hasta: fecha final en formato YYYY-MM-DD (inclusive).

    Returns:
        Lista de dicts con los emails que cumplen los filtros.
    """
    params = {}
    if destinatario:
        params["destinatario"] = destinatario
    if desde:
        params["desde"] = desde
    if hasta:
        params["hasta"] = hasta
    return _pedir("GET", "/emails/filter", params=params)


def obtener_email(email_id: int) -> dict:
    """Trae un email completo a partir de su id.

    Args:
        email_id: id numérico del email (el campo "id" que devuelven las otras tools).

    Returns:
        Dict con el email. Si el id no existe, dict con la clave "error".
    """
    return _pedir("GET", f"/emails/{email_id}")


def marcar_como_no_leido(email_id: int) -> dict:
    """Marca un email como NO leído.

    Args:
        email_id: id numérico del email.

    Returns:
        El email actualizado (leido = false). Si el id no existe, dict con "error".
    """
    return _pedir("PATCH", f"/emails/{email_id}/unread")


def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> dict:
    """Envía un email (simulado). El remitente lo pone el servidor: siempre sos vos.

    Args:
        destinatario: dirección de quien lo recibe. Ej: "jefa@empresa.com".
        asunto: asunto del mail, corto y concreto.
        cuerpo: texto completo del mail, en español, con saludo y despedida.

    Returns:
        El email creado, con su id y fecha.
    """
    payload = {"destinatario": destinatario, "asunto": asunto, "cuerpo": cuerpo}
    return _pedir("POST", "/send", json=payload)


def borrar_email(email_id: int) -> dict:
    """Borra un email de la casilla de forma definitiva.

    Args:
        email_id: id numérico del email a borrar.

    Returns:
        Dict de confirmación: {"mensaje": "Email borrado", "id": ...}. Si el id no
        existe, dict con "error".
    """
    return _pedir("DELETE", f"/emails/{email_id}")

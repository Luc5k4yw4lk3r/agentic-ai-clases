"""Helpers del lab 01 (vienen dados; no hay lógica del ejercicio acá).

- verificar_servidor(): chequea que el servidor de email esté levantado.
- reset_database(): vuelve la casilla a los 6 mails iniciales.
- mostrar_emails(lista): imprime una tabla compacta.
- mostrar_schema(tool): muestra el schema JSON que aisuite arma a partir de una función.
- resumir(obj): versión corta de un dict/lista para imprimir en la traza.
- respuesta_simulada(): un objeto con la misma forma que devuelve aisuite, para
  probar mostrar_traza() sin gastar llamadas.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

BASE_URL = os.getenv("M3_EMAIL_SERVER_API_URL", "http://localhost:8000").rstrip("/")
MI_EMAIL = "vos@empresa.com"


def verificar_servidor() -> bool:
    """Imprime un diagnóstico del servidor de email y devuelve True si está OK."""
    try:
        r = requests.get(f"{BASE_URL}/emails", timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"FALLA  No hay nada escuchando en {BASE_URL}.")
        print("       Desde M3-tool-use/ corré:  uvicorn email_server.main:app --reload --port 8000")
        return False
    if r.status_code != 200:
        print(f"FALLA  {BASE_URL}/emails respondió {r.status_code}. ¿La URL del .env apunta a otro servidor?")
        return False
    try:
        emails = r.json()
    except ValueError:
        print(f"FALLA  {BASE_URL}/emails no devolvió JSON. ¿Es el servidor correcto?")
        return False
    print(f"OK     Servidor de email en {BASE_URL} — {len(emails)} mails en la casilla")
    return True


def reset_database() -> dict:
    """Vuelve la casilla al estado inicial (6 mails) y devuelve la confirmación."""
    r = requests.get(f"{BASE_URL}/reset_database", timeout=5)
    r.raise_for_status()
    return r.json()


def mostrar_emails(emails: list[dict]) -> None:
    """Imprime los emails como tabla: id, leído, remitente, asunto, fecha."""
    if isinstance(emails, dict):  # una tool devolvió {"error": ...}
        print(emails)
        return
    if not emails:
        print("(ningún email)")
        return
    print(f"{'id':>3}  {'':2} {'remitente':<30} {'asunto':<42} fecha")
    for e in emails:
        marca = "  " if e.get("leido") else "* "
        print(f"{e['id']:>3}  {marca} {e['remitente']:<30} {e['asunto'][:42]:<42} {str(e['fecha'])[:16]}")
    print("(* = no leído)")


def mostrar_schema(tool) -> None:
    """Muestra el schema JSON que aisuite genera para una función (firma + docstring)."""
    from aisuite.utils.tools import Tools

    schema = Tools([tool]).tools()[0]
    print(json.dumps(schema, indent=2, ensure_ascii=False))


def resumir(obj, max_chars: int = 220) -> str:
    """Devuelve una versión corta (texto) de un dict/lista para la traza."""
    if isinstance(obj, list):
        texto = f"lista de {len(obj)} elemento(s): " + json.dumps(obj, ensure_ascii=False)
    else:
        texto = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    if len(texto) > max_chars:
        return texto[: max_chars - 3] + "..."
    return texto


def _msg_con_tool_call(call_id: str, nombre: str, args: dict):
    """Imita un ChatCompletionMessage del SDK con una tool_call."""
    call = SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=nombre, arguments=json.dumps(args, ensure_ascii=False)),
    )
    return SimpleNamespace(role="assistant", content=None, tool_calls=[call])


def _msg_tool(call_id: str, nombre: str, resultado) -> dict:
    """Imita el mensaje de rol "tool" que aisuite agrega después de ejecutar una tool."""
    return {"role": "tool", "name": nombre, "content": json.dumps(resultado, ensure_ascii=False), "tool_call_id": call_id}


def respuesta_simulada():
    """Un `response` con la misma forma que devuelve aisuite con max_turns.

    Sirve para probar mostrar_traza() sin servidor ni API key. Simula:
    buscar_no_leidos_de("jefa@empresa.com") -> marcar_como_leido(3) -> respuesta final.
    """
    mail = {
        "id": 3,
        "remitente": "jefa@empresa.com",
        "destinatario": MI_EMAIL,
        "asunto": "Reporte trimestral",
        "cuerpo": "Hola, ¿me pasás el reporte del Q3 antes del jueves?",
        "fecha": "2026-10-15T10:12:33",
        "leido": False,
    }
    final = SimpleNamespace(
        role="assistant",
        content="Encontré 1 mail no leído de jefa@empresa.com (\"Reporte trimestral\") y lo marqué como leído.",
        tool_calls=None,
    )
    intermedios = [
        _msg_con_tool_call("call_1", "buscar_no_leidos_de", {"remitente": "jefa@empresa.com"}),
        _msg_tool("call_1", "buscar_no_leidos_de", [mail]),
        _msg_con_tool_call("call_2", "marcar_como_leido", {"email_id": 3}),
        _msg_tool("call_2", "marcar_como_leido", {**mail, "leido": True}),
        final,
    ]
    choice = SimpleNamespace(message=final, intermediate_messages=intermedios)
    return SimpleNamespace(choices=[choice])

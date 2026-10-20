"""Helpers de presentación y parseo para el lab 01 de M5 (vienen dados).

- ``print_html(contenido, title=...)``: muestra DataFrames, dicts y texto dentro de
  una tarjeta en el notebook. Fuera de Jupyter (por ejemplo en los tests) cae a
  ``print``.
- ``parsear_json(texto)``: ``json.loads`` con un intento de reparación de escapes
  inválidos y un ``ValueError`` en español si no se puede.
- ``resumen_reporte(reporte)``: convierte el reporte del executor en texto legible.
"""
from __future__ import annotations

import json
import re
from html import escape
from typing import Any

import pandas as pd

try:  # dentro de Jupyter
    from IPython.display import HTML, display

    _EN_NOTEBOOK = True
except ImportError:  # pragma: no cover - fuera de Jupyter
    _EN_NOTEBOOK = False


def _a_texto(contenido: Any) -> str:
    if isinstance(contenido, (dict, list)):
        return json.dumps(contenido, indent=2, ensure_ascii=False, default=str)
    return str(contenido)


def print_html(contenido: Any, title: str | None = None) -> None:
    """Muestra ``contenido`` en una tarjeta con título. DataFrames como tabla; el resto como texto."""
    if not _EN_NOTEBOOK:
        if title:
            print(f"=== {title} ===")
        if isinstance(contenido, pd.DataFrame):
            print(contenido.to_string(index=False))
        else:
            print(_a_texto(contenido))
        print()
        return

    if isinstance(contenido, pd.DataFrame):
        cuerpo = contenido.to_html(classes="tarjeta-tabla", index=False, border=0)
    else:
        cuerpo = f"<pre><code>{escape(_a_texto(contenido))}</code></pre>"
    css = """
    <style>
    .tarjeta { font-family: ui-sans-serif, system-ui; border: 1px solid #cbd5e1; border-left: 6px solid #2563eb;
               border-radius: 8px; padding: 12px 14px; margin: 8px 0; background: #fff; color: #111; }
    .tarjeta-titulo { font-weight: 700; margin-bottom: 6px; font-size: 14px; }
    .tarjeta pre, .tarjeta code { background: #f3f4f6; color: #111; padding: 8px; border-radius: 6px;
               display: block; overflow-x: auto; font-size: 13px; white-space: pre-wrap; }
    .tarjeta table.tarjeta-tabla { border-collapse: collapse; width: 100%; font-size: 13px; color: #111; }
    .tarjeta table.tarjeta-tabla th, .tarjeta table.tarjeta-tabla td { border: 1px solid #e5e7eb; padding: 5px 8px; text-align: left; }
    .tarjeta table.tarjeta-tabla th { background: #f9fafb; }
    </style>
    """
    titulo_html = f'<div class="tarjeta-titulo">{escape(title)}</div>' if title else ""
    display(HTML(css + f'<div class="tarjeta">{titulo_html}{cuerpo}</div>'))


_ESCAPES_VALIDOS = r'["\\/bfnrtu]'


def _reparar_escapes(texto: str) -> str:
    """Quita barras invertidas que no forman un escape JSON válido (``\\'`` o ``\\$``)."""
    texto = texto.replace("\\'", "'")
    return re.sub(rf"\\(?!{_ESCAPES_VALIDOS})", "", texto)


def parsear_json(texto: str) -> dict:
    """Convierte el texto que devolvió el modelo en un dict.

    Primero intenta ``json.loads`` directo; si falla, intenta reparar escapes
    inválidos (un error frecuente del modelo). Si tampoco así se puede, levanta
    ``ValueError`` con el comienzo del texto para que se vea qué vino.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("El modelo devolvió una respuesta vacía; se esperaba un JSON.")
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        try:
            datos = json.loads(_reparar_escapes(texto))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"No pude interpretar la respuesta del modelo como JSON ({e.msg}). "
                f"Empieza así: {texto[:200]!r}"
            ) from e
    if not isinstance(datos, dict):
        raise ValueError(f"Se esperaba un objeto JSON (dict) y llegó {type(datos).__name__}.")
    return datos


def resumen_reporte(reporte: dict[str, Any]) -> str:
    """Resume el reporte del executor en líneas legibles (sin DataFrames adentro)."""
    lineas = [f"Estado general: {'OK' if reporte.get('ok') else 'FALLÓ'}"]
    for paso in reporte.get("steps", []):
        estado = "ok" if paso.get("ok") else "FALLÓ"
        lineas.append(f"  Paso {paso.get('step_number')}: {paso.get('description')}  [{estado}]")
        lineas.append(f"      tools: {paso.get('tools_run')}")
        if paso.get("tool_error"):
            lineas.append(f"      error de tool: {paso['tool_error']}")
        for v in paso.get("validations", []):
            detalle = v.get("error") or {k: val for k, val in v.get("result", {}).items() if k != "ok"}
            lineas.append(f"      validación '{v.get('name')}': {'ok' if v.get('ok') else 'FALLÓ'} {detalle if detalle else ''}")
    if reporte.get("aborted"):
        lineas.append(f"  Abortado en el paso {reporte.get('abort_step')} por: {reporte.get('abort_reason')}")
    return "\n".join(lineas)

"""Helpers de presentación para el lab 02 de M5 (vienen dados).

- ``print_html(contenido, title=...)``: tarjeta en el notebook con texto, JSON o código.
  Fuera de Jupyter cae a ``print``.
- ``mostrar_tabla(tbl, title=...)``: imprime una tabla TinyDB como JSON legible.
"""
from __future__ import annotations

import json
from html import escape
from typing import Any

try:  # dentro de Jupyter
    from IPython.display import HTML, display

    _EN_NOTEBOOK = True
except ImportError:  # pragma: no cover
    _EN_NOTEBOOK = False


def _a_texto(contenido: Any) -> str:
    if isinstance(contenido, (dict, list)):
        return json.dumps(contenido, indent=2, ensure_ascii=False, default=str)
    return str(contenido)


def print_html(contenido: Any, title: str | None = None, es_codigo: bool = False) -> None:
    """Muestra ``contenido`` en una tarjeta. ``es_codigo=True`` cambia el color del borde."""
    texto = _a_texto(contenido)
    if not _EN_NOTEBOOK:
        if title:
            print(f"=== {title} ===")
        print(texto)
        print()
        return
    borde = "#7c3aed" if es_codigo else "#2563eb"
    css = f"""
    <style>
    .tarjeta2 {{ font-family: ui-sans-serif, system-ui; border: 1px solid #cbd5e1; border-left: 6px solid {borde};
                 border-radius: 8px; padding: 12px 14px; margin: 8px 0; background: #fff; color: #111; }}
    .tarjeta2-titulo {{ font-weight: 700; margin-bottom: 6px; font-size: 14px; }}
    .tarjeta2 pre {{ background: #f3f4f6; color: #111; padding: 8px; border-radius: 6px; overflow-x: auto;
                     font-size: 13px; white-space: pre-wrap; margin: 0; }}
    </style>
    """
    titulo_html = f'<div class="tarjeta2-titulo">{escape(title)}</div>' if title else ""
    display(HTML(css + f'<div class="tarjeta2">{titulo_html}<pre>{escape(texto)}</pre></div>'))


def mostrar_tabla(tbl, title: str | None = None, campos: list[str] | None = None) -> None:
    """Imprime las filas de una tabla TinyDB. ``campos`` limita las columnas (para no ver descripciones largas)."""
    filas = tbl.all()
    if campos:
        filas = [{k: fila.get(k) for k in campos} for fila in filas]
    print_html(filas, title=title)


def quitar_fences(codigo: str) -> str:
    """Si el código viene envuelto en ```python ... ``` (dentro de las etiquetas), saca las fences."""
    texto = codigo.strip()
    if texto.startswith("```"):
        primera_linea_fin = texto.find("\n")
        texto = texto[primera_linea_fin + 1 :] if primera_linea_fin != -1 else ""
    if texto.rstrip().endswith("```"):
        texto = texto.rstrip()[: -3]
    return texto.strip()

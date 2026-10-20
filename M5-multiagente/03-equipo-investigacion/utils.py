"""Helpers del lab 03 de M5 (vienen dados).

- ``limpiar_json(texto)``: saca fences de markdown (```json ... ```) y texto alrededor
  de un JSON para que ``json.loads`` lo pueda leer. Levanta ``ValueError`` en español si
  no encuentra nada que parezca JSON.
- ``quitar_fences(texto)``: saca un envoltorio ```markdown ... ``` de un texto largo (para
  el informe final).
- ``mostrar_markdown(texto)`` / ``print_html(...)``: presentación en el notebook.
- ``guardar_informe(texto, ruta)``: escribe el informe final en ``data/informe.md``.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

try:  # dentro de Jupyter
    from IPython.display import HTML, Markdown, display

    _EN_NOTEBOOK = True
except ImportError:  # pragma: no cover
    _EN_NOTEBOOK = False

_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n?|\n?```\s*$")


def limpiar_json(texto: str) -> str:
    """Deja solo el JSON de una respuesta del modelo.

    Maneja los tres casos típicos:
    1. JSON limpio → se devuelve tal cual (sin espacios de más).
    2. JSON dentro de fences ```json ... ``` → se quitan las fences.
    3. Texto antes o después ("Acá va el plan: [...] Espero que sirva") → se recorta
       desde el primer ``[`` o ``{`` hasta el último ``]`` o ``}`` que cierre.

    No valida que el resultado sea JSON válido: eso lo hace ``json.loads`` después, y así
    el error de parseo apunta al texto real.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("La respuesta del modelo está vacía; se esperaba un JSON.")
    limpio = texto.strip()
    limpio = _FENCE.sub("", limpio).strip()
    # Recortar texto alrededor: desde la primera apertura hasta el último cierre del mismo tipo
    inicio_lista = limpio.find("[")
    inicio_obj = limpio.find("{")
    candidatos = [i for i in (inicio_lista, inicio_obj) if i != -1]
    if not candidatos:
        raise ValueError(f"No encontré un JSON (ni '[' ni '{{') en la respuesta. Empieza así: {texto[:150]!r}")
    inicio = min(candidatos)
    cierre = "]" if limpio[inicio] == "[" else "}"
    fin = limpio.rfind(cierre)
    if fin == -1 or fin < inicio:
        raise ValueError(f"El JSON parece abrir con '{limpio[inicio]}' pero no cierra. Empieza así: {texto[:150]!r}")
    return limpio[inicio : fin + 1]


def print_html(contenido: Any, title: str | None = None) -> None:
    """Muestra texto o JSON en una tarjeta (o con print fuera de Jupyter)."""
    texto = json.dumps(contenido, indent=2, ensure_ascii=False) if isinstance(contenido, (dict, list)) else str(contenido)
    if not _EN_NOTEBOOK:
        if title:
            print(f"=== {title} ===")
        print(texto)
        print()
        return
    css = """
    <style>
    .tarjeta3 { font-family: ui-sans-serif, system-ui; border: 1px solid #cbd5e1; border-left: 6px solid #0f766e;
                border-radius: 8px; padding: 12px 14px; margin: 8px 0; background: #fff; color: #111; }
    .tarjeta3-titulo { font-weight: 700; margin-bottom: 6px; font-size: 14px; }
    .tarjeta3 pre { background: #f3f4f6; color: #111; padding: 8px; border-radius: 6px; overflow-x: auto;
                    font-size: 13px; white-space: pre-wrap; margin: 0; }
    </style>
    """
    titulo_html = f'<div class="tarjeta3-titulo">{escape(title)}</div>' if title else ""
    display(HTML(css + f'<div class="tarjeta3">{titulo_html}<pre>{escape(texto)}</pre></div>'))


def mostrar_markdown(texto: str) -> None:
    """Renderiza Markdown en el notebook; fuera de Jupyter lo imprime."""
    if _EN_NOTEBOOK:
        display(Markdown(texto))
    else:
        print(texto)


def guardar_informe(texto: str, ruta: str | Path = "data/informe.md") -> Path:
    """Guarda el informe en disco (crea la carpeta si no existe) y devuelve la ruta."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto.strip() + "\n", encoding="utf-8")
    return ruta


def resumen_historial(historial: list[tuple[str, str, str]], ancho: int = 160) -> str:
    """Una línea por paso: número, agente y el comienzo de la salida."""
    lineas = []
    for i, (paso, agente, salida) in enumerate(historial, start=1):
        primera = " ".join(str(salida).split())[:ancho]
        lineas.append(f"{i}. [{agente}] {paso}\n     → {primera}{'...' if len(str(salida)) > ancho else ''}")
    return "\n".join(lineas)


def quitar_fences(texto: str) -> str:
    """Si el texto completo viene envuelto en ``` ... ``` (con o sin lenguaje), saca las fences."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        salto = limpio.find("\n")
        limpio = limpio[salto + 1 :] if salto != -1 else ""
    if limpio.rstrip().endswith("```"):
        limpio = limpio.rstrip()[:-3]
    return limpio.strip()

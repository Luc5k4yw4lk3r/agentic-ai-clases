"""Helpers de visualización para el lab 01 de M4 (sin lógica del ejercicio).

- ``mostrar_html``: muestra HTML **sin escaparlo** dentro de una tarjeta.
  El ``print_html`` del material original escapaba todo, así que las etiquetas
  (``<h3>``, ``<pre>``) aparecían como texto plano.
- ``mostrar_texto``: lo contrario, texto plano escapado en un ``<pre>``.
- ``mostrar_markdown``: renderiza Markdown (lo que devuelve el LLM).
- ``resumen_html``: arma la tarjeta PASS/FAIL a partir del dict que devuelve
  ``evaluar_referencias``.
"""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
from IPython.display import HTML, Markdown, display

_CSS = """
<style>
.tarjeta { font-family: ui-sans-serif, system-ui; border: 1px solid #d0d7de; border-left: 6px solid #3b82f6;
           border-radius: 8px; padding: 12px 16px; margin: 10px 0; background: #fff; color: #111; }
.tarjeta-titulo { font-weight: 700; margin-bottom: 8px; font-size: 14px; }
.tarjeta pre { background: #f6f8fa; padding: 8px; border-radius: 6px; white-space: pre-wrap; font-size: 13px; }
.tarjeta table { border-collapse: collapse; width: 100%; font-size: 13px; }
.tarjeta th, .tarjeta td { border: 1px solid #e5e7eb; padding: 4px 8px; text-align: left; }
.tarjeta th { background: #f9fafb; }
.tarjeta.ok { border-left-color: #16a34a; }
.tarjeta.fail { border-left-color: #dc2626; }
</style>
"""


def _tarjeta(cuerpo_html: str, titulo: str | None, clase: str = "") -> None:
    titulo_html = f'<div class="tarjeta-titulo">{escape(titulo)}</div>' if titulo else ""
    display(HTML(_CSS + f'<div class="tarjeta {clase}">{titulo_html}{cuerpo_html}</div>'))


def mostrar_html(contenido: Any, titulo: str | None = None) -> None:
    """Muestra ``contenido`` como HTML dentro de una tarjeta. NO escapa las etiquetas.

    Acepta un string con HTML o un DataFrame (se convierte a tabla).
    """
    if isinstance(contenido, pd.DataFrame):
        cuerpo = contenido.to_html(index=False, border=0, escape=True)
    else:
        cuerpo = str(contenido)
    _tarjeta(cuerpo, titulo)


def mostrar_texto(texto: Any, titulo: str | None = None) -> None:
    """Muestra texto plano (escapado) en un ``<pre>``. Útil para JSON o salidas crudas."""
    _tarjeta(f"<pre>{escape(str(texto))}</pre>", titulo)


def mostrar_markdown(texto: str, titulo: str | None = None) -> None:
    """Renderiza Markdown (por ejemplo, la lista de referencias que devuelve el LLM)."""
    if titulo:
        display(Markdown(f"### {titulo}"))
    display(Markdown(texto or "*(vacío)*"))


def resumen_html(resultado: dict, umbral: float) -> str:
    """Convierte el dict de ``evaluar_referencias`` en una tarjeta HTML con PASS/FAIL y detalle.

    ``resultado`` tiene las claves ``total``, ``confiables``, ``ratio``, ``aprobado`` y
    ``detalle`` (lista de tuplas ``(url, dominio, ok)``).
    """
    estado = "PASS" if resultado["aprobado"] else "FAIL"
    filas = []
    for url, dominio, ok in resultado["detalle"]:
        marca = "confiable" if ok else "no confiable"
        filas.append(
            f"<tr><td><a href='{escape(url)}' target='_blank'>{escape(url)}</a></td>"
            f"<td>{escape(dominio)}</td><td>{marca}</td></tr>"
        )
    tabla = (
        "<table><tr><th>URL</th><th>Dominio</th><th>Resultado</th></tr>" + "".join(filas) + "</table>"
        if filas
        else "<p>No se detectaron URLs en el texto.</p>"
    )
    return (
        f"<p><strong>Estado: {estado}</strong> — {resultado['confiables']} de {resultado['total']} URLs "
        f"en dominios confiables (ratio {resultado['ratio']:.0%}, umbral {umbral:.0%}).</p>" + tabla
    )


def mostrar_evaluacion(resultado: dict, umbral: float, titulo: str = "Evaluación de fuentes") -> None:
    """Muestra la tarjeta PASS/FAIL con borde verde o rojo."""
    _tarjeta(resumen_html(resultado, umbral), titulo, clase="ok" if resultado["aprobado"] else "fail")

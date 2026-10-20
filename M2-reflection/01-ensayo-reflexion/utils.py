"""Helpers del lab 01 — Ensayo con reflexión.

Acá no hay lógica del ejercicio: solo funciones para mostrar texto de forma
cómoda dentro del notebook. Si las leés, no te vas a encontrar con nada que
tengas que completar.
"""
from __future__ import annotations

from html import escape

try:
    from IPython.display import HTML, display
except ImportError:  # fuera de Jupyter (por ejemplo, en pytest)
    HTML = None
    display = None


COLORES = {
    "borrador": "#fff8dc",   # amarillo suave
    "critica": "#e0f7fa",    # celeste
    "revision": "#f3e5f5",   # lila
    "neutro": "#f5f5f5",
}


def mostrar_caja(titulo: str, contenido: str, color: str = COLORES["neutro"]) -> None:
    """Muestra `contenido` dentro de una caja con título, para comparar versiones.

    Si no estamos en Jupyter (por ejemplo, corriendo un script), imprime texto plano.
    El contenido se escapa con `html.escape` para que un ensayo con `<` o `&`
    no rompa el HTML (el helper original no lo hacía).
    """
    if display is None or HTML is None:
        print(f"\n===== {titulo} =====\n{contenido}\n")
        return
    html = f"""
    <div style="border:1px solid #ccc; border-radius:10px; padding:15px;
                margin-bottom:15px; background-color:{color}; color:#222;">
        <h3 style="margin-top:0;">{escape(titulo)}</h3>
        <pre style="white-space:pre-wrap; font-family:system-ui, sans-serif;
                    font-size:14px;">{escape(contenido)}</pre>
    </div>
    """
    display(HTML(html))


def contar_palabras(texto: str) -> int:
    """Cantidad de palabras de un texto (separadas por espacios)."""
    return len(texto.split())


def resumen_versiones(borradores: list[str]) -> str:
    """Arma una tabla de texto con el largo de cada versión del ensayo."""
    lineas = ["versión | palabras"]
    for i, texto in enumerate(borradores):
        lineas.append(f"V{i + 1}      | {contar_palabras(texto)}")
    return "\n".join(lineas)

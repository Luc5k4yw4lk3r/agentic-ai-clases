"""Helpers del lab 03 — Gráficos con reflexión multimodal.

Vienen dados: no hay lógica del ejercicio acá.

- `cargar_datos(ruta_csv)`: lee el CSV de ventas de café y deriva año, trimestre y mes.
- `describir_columnas(df)`: texto con las columnas reales del DataFrame para el prompt.
- `imagen_a_data_url(ruta_png)`: codifica un PNG en base64 como data URL para la API.
- `extraer_json(texto)`: igual que en el lab 02 (tolera fences; ValueError si no hay JSON).
- `borrar_pngs(carpeta)`: limpia los gráficos de corridas anteriores.
- `mostrar_html(contenido, titulo, estilo)`: tarjeta para texto, DataFrames o imágenes.
"""
from __future__ import annotations

import base64
import json
import re
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from IPython.display import HTML, display
except ImportError:  # fuera de Jupyter
    HTML = None
    display = None


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def cargar_datos(ruta_csv: str = "data/coffee_sales.csv") -> pd.DataFrame:
    """Carga el CSV de ventas de café y agrega columnas derivadas de la fecha.

    Columnas originales (tal como están en el archivo):
      date (YYYY-MM-DD), time (HH:MM), cash_type ('card' o 'cash'),
      card (identificador anonimizado; vacío en pagos en efectivo),
      price (número, precio pagado), coffee_name (nombre de la bebida).

    Columnas derivadas: year, quarter (1-4), month (1-12).
    """
    df = pd.read_csv(ruta_csv)
    if "date" not in df.columns:
        raise ValueError(f"El CSV {ruta_csv} no tiene la columna 'date'. Columnas: {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise")
    df["year"] = df["date"].dt.year
    df["quarter"] = df["date"].dt.quarter
    df["month"] = df["date"].dt.month
    return df


def describir_columnas(df: pd.DataFrame) -> str:
    """Arma la descripción de columnas para el prompt a partir del DataFrame real.

    Se genera desde los datos (no a mano) para que el prompt nunca nombre columnas
    que no existen ni formatos equivocados: el lab original describía columnas
    inexistentes y una fecha en formato M/D/YY cuando el archivo trae YYYY-MM-DD.
    """
    descripciones = {
        "date": "fecha de la venta (datetime, ya parseada)",
        "time": "hora de la venta, texto HH:MM",
        "cash_type": "medio de pago: 'card' o 'cash'",
        "card": "identificador anonimizado de la tarjeta (vacío si fue efectivo)",
        "price": "precio pagado (número)",
        "coffee_name": "nombre de la bebida",
        "year": "año (entero)",
        "quarter": "trimestre 1-4 (entero)",
        "month": "mes 1-12 (entero)",
    }
    lineas = []
    for columna in df.columns:
        tipo = str(df[columna].dtype)
        detalle = descripciones.get(columna, "")
        lineas.append(f"- {columna} ({tipo}): {detalle}".rstrip(": "))
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Imágenes
# ---------------------------------------------------------------------------
def imagen_a_data_url(ruta_png: str) -> str:
    """Lee un PNG y lo devuelve como data URL (`data:image/png;base64,...`).

    Es el formato que la API de OpenAI acepta en `image_url` para mandar una imagen
    local sin subirla a ningún lado.
    """
    ruta = Path(ruta_png)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta_png}. El código del gráfico tiene que haberse ejecutado sin errores "
            "y haber guardado la figura en esa ruta."
        )
    datos = ruta.read_bytes()
    if not datos.startswith(b"\x89PNG"):
        raise ValueError(f"{ruta_png} no parece un PNG válido (cabecera incorrecta).")
    b64 = base64.b64encode(datos).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def borrar_pngs(carpeta: str = "data") -> list[str]:
    """Borra los PNG de corridas anteriores para no mostrar un gráfico viejo por error.

    Devuelve la lista de archivos borrados.
    """
    borrados = []
    for ruta in Path(carpeta).glob("*.png"):
        ruta.unlink()
        borrados.append(str(ruta))
    return borrados


# ---------------------------------------------------------------------------
# Parseo de la respuesta del modelo
# ---------------------------------------------------------------------------
def extraer_json(texto: str) -> dict:
    """Extrae un objeto JSON de la respuesta de un LLM.

    Acepta JSON puro, JSON dentro de ```json ... ``` y JSON rodeado de prosa.
    Levanta ValueError (en español) si no encuentra un objeto JSON válido.

    Importante para este lab: el JSON viene ANTES del bloque <execute_python>.
    Buscamos solo hasta la primera aparición de la etiqueta para no confundirnos con
    llaves `{}` que puedan aparecer dentro del código Python.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("La respuesta del modelo está vacía: no hay JSON para extraer.")

    zona = texto.split("<execute_python>")[0]

    try:
        obj = json.loads(zona)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", zona, flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    inicio = zona.find("{")
    fin = zona.rfind("}")
    if inicio != -1 and fin > inicio:
        try:
            obj = json.loads(zona[inicio:fin + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    recorte = texto.strip().replace("\n", " ")[:200]
    raise ValueError(
        "No pude extraer un objeto JSON de la respuesta del modelo (antes de <execute_python>). "
        f"La respuesta empezaba así: {recorte!r}"
    )


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
_CSS = """
<style>
.tarjeta{font-family:system-ui,sans-serif;border:1px solid #d0d7de;border-left:6px solid #3b82f6;
         border-radius:8px;padding:12px 14px;margin:10px 0;background:#fff;color:#111;}
.tarjeta .titulo{font-weight:700;margin-bottom:8px;font-size:14px;}
.tarjeta pre{background:#f6f8fa;color:#111;padding:8px;border-radius:6px;overflow-x:auto;
             font-size:13px;white-space:pre-wrap;margin:0;}
.tarjeta img{max-width:100%;height:auto;border-radius:6px;}
.tarjeta table{border-collapse:collapse;width:100%;font-size:13px;}
.tarjeta th,.tarjeta td{border:1px solid #e5e7eb;padding:5px 8px;text-align:left;}
.tarjeta th{background:#f3f4f6;font-weight:600;}
.tarjeta.ok{border-left-color:#16a34a;} .tarjeta.alerta{border-left-color:#dc2626;}
</style>
"""


def mostrar_html(contenido: Any, titulo: str | None = None, estilo: str = "", es_imagen: bool = False) -> None:
    """Muestra texto, un DataFrame o una imagen (ruta a PNG) dentro de una tarjeta.

    `estilo`: "" (azul), "ok" (verde) o "alerta" (rojo). Fuera de Jupyter imprime texto.
    """
    if display is None or HTML is None:
        print(f"\n===== {titulo or ''} =====")
        if es_imagen:
            print(f"[imagen: {contenido}]")
        elif isinstance(contenido, pd.DataFrame):
            print(contenido.to_string(index=False))
        else:
            print(contenido)
        return
    if es_imagen and isinstance(contenido, str):
        cuerpo = f'<img src="{imagen_a_data_url(contenido)}" alt="{escape(titulo or "gráfico")}">'
    elif isinstance(contenido, pd.DataFrame):
        cuerpo = contenido.to_html(index=False, border=0, escape=True)
    else:
        cuerpo = f"<pre>{escape(str(contenido))}</pre>"
    cabecera = f'<div class="titulo">{escape(titulo)}</div>' if titulo else ""
    display(HTML(_CSS + f'<div class="tarjeta {estilo}">{cabecera}{cuerpo}</div>'))

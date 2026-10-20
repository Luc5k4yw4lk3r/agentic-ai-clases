"""Helpers del lab 02 — SQL con reflexión.

Vienen dados: no hay lógica del ejercicio acá. Lo que sí conviene leer es
`extraer_json`, porque es la pieza que evita que una respuesta mal formateada
del modelo pase desapercibida.

- `crear_db_transacciones(db_path)`: genera la base SQLite de eventos (seed fija).
- `obtener_schema(db_path)`: devuelve el schema de la tabla como texto para el prompt.
- `ejecutar_sql(sql, db_path)`: corre una consulta y devuelve un DataFrame.
- `extraer_json(texto)`: saca un objeto JSON de la respuesta del modelo, aunque venga
  envuelto en ```json ... ``` o con texto alrededor. Levanta ValueError si no hay JSON.
- `limpiar_sql(sql)`: saca fences ```sql ... ``` que a veces agrega el modelo.
- `misma_sql(a, b)`: compara dos consultas ignorando espacios/mayúsculas/fences.
- `mostrar_html(contenido, titulo, estilo)`: tarjeta HTML para texto o DataFrames.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
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
# Base de datos
# ---------------------------------------------------------------------------
def crear_db_transacciones(
    db_path: str = "data/productos.db",
    n_productos: int = 100,
    n_eventos_por_producto: int = 50,
    seed: int = 42,
) -> str:
    """Crea una base SQLite con una sola tabla `transactions` de eventos.

    Cada fila es un **evento** sobre un producto: alta inicial ('insert'),
    reposición ('restock'), venta ('sale') o cambio de precio ('price_update').
    No hay tabla de stock ni de ventas: todo se deriva sumando eventos.

    Convención de signos (importante para el lab):
      - qty_delta > 0 en insert y restock (entra mercadería),
      - qty_delta < 0 en sale (sale mercadería),
      - qty_delta = 0 en price_update.
      - unit_price es el precio vigente en ese momento; NULL en restock.

    Con el mismo `seed` la base es idéntica en todas las máquinas.
    Devuelve la ruta del archivo creado.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS transactions")
    cur.execute(
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            color TEXT NOT NULL,
            action TEXT NOT NULL,            -- 'insert' | 'restock' | 'sale' | 'price_update'
            qty_delta INTEGER DEFAULT 0,     -- + para insert/restock, - para sale, 0 para price_update
            unit_price REAL,                 -- precio en ese momento (NULL en restock)
            notes TEXT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    marcas = ["Nike", "Adidas", "Puma", "Reebok", "New Balance"]
    categorias = ["shoes", "hoodie", "t-shirt", "hat", "backpack"]
    colores = ["black", "white", "red", "blue", "green"]

    rng = random.Random(seed)
    catalogo = []
    for pid in range(1, n_productos + 1):
        marca = rng.choice(marcas)
        categoria = rng.choice(categorias)
        color = rng.choice(colores)
        precio_base = round(rng.uniform(20.0, 150.0), 2)
        catalogo.append((pid, f"{marca} {categoria}", marca, categoria, color, precio_base))

    insert = """
        INSERT INTO transactions
            (product_id, product_name, brand, category, color, action, qty_delta, unit_price, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for pid, nombre, marca, categoria, color, precio_base in catalogo:
        stock_inicial = rng.randint(5, 50)
        cur.execute(insert, (pid, nombre, marca, categoria, color, "insert", stock_inicial, precio_base,
                             f"Alta inicial: stock={stock_inicial}, precio={precio_base}"))
        precio_actual = precio_base
        for _ in range(n_eventos_por_producto - 1):
            tipo = rng.choices(["restock", "sale", "price_update"], weights=[0.25, 0.6, 0.15], k=1)[0]
            if tipo == "restock":
                qty = rng.randint(1, 25)
                cur.execute(insert, (pid, nombre, marca, categoria, color, "restock", qty, None,
                                     f"Reposición +{qty} unidades"))
            elif tipo == "sale":
                qty = -rng.randint(1, 10)  # negativo: sale mercadería
                cur.execute(insert, (pid, nombre, marca, categoria, color, "sale", qty, precio_actual,
                                     f"Venta de {-qty} unidades a {precio_actual}"))
            else:
                delta = round(rng.uniform(-5.0, 5.0), 2)
                precio_actual = max(1.0, round(precio_actual + delta, 2))
                cur.execute(insert, (pid, nombre, marca, categoria, color, "price_update", 0, precio_actual,
                                     f"Nuevo precio: {precio_actual}"))
    conn.commit()
    conn.close()
    return db_path


def obtener_schema(db_path: str) -> str:
    """Devuelve el schema de `transactions` como texto plano para pegar en un prompt."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(transactions)")
    filas = cur.fetchall()
    conn.close()
    if not filas:
        raise ValueError(f"La base {db_path} no tiene la tabla `transactions`. Corré crear_db_transacciones() primero.")
    lineas = ["Tabla: transactions"]
    for fila in filas:
        nombre, tipo = fila[1], fila[2]
        lineas.append(f"  {nombre} ({tipo})")
    return "\n".join(lineas)


def limpiar_sql(sql: str) -> str:
    """Saca los fences ```sql ... ``` o ``` ... ``` que el modelo a veces agrega."""
    texto = sql.strip()
    texto = re.sub(r"^```(?:sql)?\s*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def misma_sql(a: str, b: str) -> bool:
    """True si las dos consultas son iguales ignorando fences, espacios y mayúsculas.

    Sirve para saber si la reflexión cambió algo de verdad, en vez de asumirlo.
    """
    norm_a = " ".join(limpiar_sql(a).split()).lower().rstrip(";")
    norm_b = " ".join(limpiar_sql(b).split()).lower().rstrip(";")
    return norm_a == norm_b


def ejecutar_sql(sql: str, db_path: str) -> pd.DataFrame:
    """Ejecuta una consulta SELECT y devuelve el resultado como DataFrame.

    Si la consulta falla (sintaxis, columna inexistente), devuelve un DataFrame de
    una columna `error` con el mensaje. Así el flujo puede seguir y la reflexión
    puede ver el error como feedback, en lugar de cortar el notebook.
    """
    consulta = limpiar_sql(sql)
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(consulta, conn)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Parseo de la respuesta del modelo
# ---------------------------------------------------------------------------
def extraer_json(texto: str) -> dict:
    """Extrae un objeto JSON de la respuesta de un LLM.

    Acepta:
      - JSON puro: `{"feedback": "...", "sql_refinado": "..."}`
      - JSON dentro de fences: ```json { ... } ```
      - JSON con texto antes o después ("Acá va el resultado: {...}").

    Levanta `ValueError` con un mensaje en español si no encuentra un objeto JSON
    válido. Esto es a propósito: el lab original, cuando el parseo fallaba, devolvía
    en silencio la SQL original como si fuera la "refinada", y el notebook mostraba
    V2 = V1 sin avisar.
    """
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("La respuesta del modelo está vacía: no hay JSON para extraer.")

    # 1) Intento directo
    try:
        obj = json.loads(texto)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) Dentro de un bloque ```json ... ``` (o ``` ... ```)
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 3) El primer `{` hasta el último `}` (JSON rodeado de prosa)
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin > inicio:
        try:
            obj = json.loads(texto[inicio:fin + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    recorte = texto.strip().replace("\n", " ")[:200]
    raise ValueError(
        "No pude extraer un objeto JSON de la respuesta del modelo. "
        "Revisá el prompt (pedí 'Respondé solo con un JSON') o usá response_format. "
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
.tarjeta table{border-collapse:collapse;width:100%;font-size:13px;}
.tarjeta th,.tarjeta td{border:1px solid #e5e7eb;padding:5px 8px;text-align:left;}
.tarjeta th{background:#f3f4f6;font-weight:600;}
.tarjeta.ok{border-left-color:#16a34a;} .tarjeta.alerta{border-left-color:#dc2626;}
</style>
"""


def mostrar_html(contenido: Any, titulo: str | None = None, estilo: str = "") -> None:
    """Muestra texto o un DataFrame dentro de una tarjeta con título.

    `estilo` puede ser "" (azul), "ok" (verde) o "alerta" (rojo). Fuera de Jupyter
    imprime texto plano.
    """
    if display is None or HTML is None:
        print(f"\n===== {titulo or ''} =====")
        print(contenido if not isinstance(contenido, pd.DataFrame) else contenido.to_string(index=False))
        return
    if isinstance(contenido, pd.DataFrame):
        cuerpo = contenido.to_html(index=False, border=0, escape=True)
    else:
        cuerpo = f"<pre>{escape(str(contenido))}</pre>"
    cabecera = f'<div class="titulo">{escape(titulo)}</div>' if titulo else ""
    display(HTML(_CSS + f'<div class="tarjeta {estilo}">{cabecera}{cuerpo}</div>'))

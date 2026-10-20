"""Base TinyDB de la tienda de anteojos y helpers que ve el código generado (lab 02, M5).

- ``seed_db(ruta)``: crea (o reinicia) ``data/store_db.json`` con 6 modelos y una
  transacción de apertura. Devuelve ``(db, inventory_tbl, transactions_tbl)``.
- ``construir_bloque_schema(inventory_tbl, transactions_tbl)``: describe las dos tablas
  en texto (columnas, tipos, ejemplos) para pegarlo en el prompt.
- ``get_current_balance(tbl)`` y ``next_transaction_id(tbl)``: helpers que el código
  generado por el LLM puede llamar.

Diferencias con el original: ``create_inventory``/``create_transactions`` ya no escriben
sobre tablas globales abiertas al importar el módulo (eso hacía que ``reseed`` tocara un
archivo distinto del que usaba el notebook); ahora reciben la tabla como parámetro.
"""
from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

from tinydb import TinyDB
from tinydb.table import Table

RUTA_DB = Path(__file__).resolve().parent / "data" / "store_db.json"

PRODUCTOS = [
    ("SG001", "Aviator", 80,
     "Diseñados originalmente para pilotos: lentes en forma de gota y marco metálico fino. "
     "Cobertura amplia y construcción liviana para uso prolongado."),
    ("SG002", "Wayfarer", 95,
     "Marco grueso y angular que marca presencia. Aire retro con un toque moderno; lentes "
     "rectangulares y acetato resistente."),
    ("SG003", "Mystique", 70,
     "Inspirados en el glamour de los años 50: el marco se eleva en las puntas y dibuja una "
     "silueta elegante. Patillas con detalles."),
    ("SG004", "Sport", 110,
     "Pensados para deportes: una sola lente curva envolvente que protege del viento. Marco "
     "flexible y liviano con grips de goma."),
    ("SG005", "Classic", 60,
     "Perfil redondo clásico con marco metálico minimalista. Un estilo atemporal que va "
     "tanto con ropa casual como formal."),
    ("SG006", "Moon", 120,
     "Estilo redondo oversize con marco plástico grueso. Estética retro con un giro moderno."),
]


def create_inventory(inventory_tbl: Table) -> list[dict[str, Any]]:
    """Vacía la tabla y carga los 6 productos. Stock con semilla fija: [23, 6, 3, 11, 10, 10]."""
    random.seed(42)
    filas = []
    for item_id, nombre, precio, descripcion in PRODUCTOS:
        filas.append({
            "item_id": item_id,
            "name": nombre,
            "description": descripcion,
            "quantity_in_stock": random.randint(3, 25),
            "price": precio,
        })
    inventory_tbl.truncate()
    inventory_tbl.insert_multiple(filas)
    return filas


def create_transactions(transactions_tbl: Table, saldo_inicial: float = 500.00) -> dict[str, Any]:
    """Vacía la tabla y carga la transacción de apertura de caja."""
    apertura = {
        "transaction_id": "TXN001",
        "customer_name": "OPENING_BALANCE",
        "transaction_summary": "Saldo de apertura de caja",
        "transaction_amount": saldo_inicial,
        "balance_after_transaction": saldo_inicial,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    transactions_tbl.truncate()
    transactions_tbl.insert(apertura)
    return apertura


def seed_db(ruta: str | Path = RUTA_DB) -> tuple[TinyDB, Table, Table]:
    """Abre (o crea) la base en ``ruta``, la reinicia con los datos iniciales y devuelve las tablas."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    db = TinyDB(ruta, ensure_ascii=False, indent=1)
    inventory_tbl = db.table("inventory")
    transactions_tbl = db.table("transactions")
    create_inventory(inventory_tbl)
    create_transactions(transactions_tbl)
    return db, inventory_tbl, transactions_tbl


# ---------------------------------------------------------------------------
# Schema en texto para el prompt
# ---------------------------------------------------------------------------


def _tipo(valor: Any) -> str:
    if isinstance(valor, bool):
        return "bool"
    if isinstance(valor, int):
        return "int"
    if isinstance(valor, float):
        return "float"
    return "str"


def describir_tabla(tbl: Table, nombre: str, ejemplos: int = 3) -> str:
    """Columnas, tipo inferido y algunos valores de ejemplo de una tabla TinyDB."""
    filas = tbl.all()
    if not filas:
        return f"TABLA: {nombre} (vacía)"
    columnas: dict[str, dict[str, Any]] = {}
    for fila in filas:
        for clave, valor in fila.items():
            if clave not in columnas:
                columnas[clave] = {"tipo": _tipo(valor), "ejemplos": []}
            if len(columnas[clave]["ejemplos"]) < ejemplos and valor not in columnas[clave]["ejemplos"]:
                columnas[clave]["ejemplos"].append(valor)
    lineas = [f"TABLA: {nombre}  ({len(filas)} filas)", "COLUMNAS:"]
    for col, info in columnas.items():
        ej = ", ".join(repr(e)[:50] for e in info["ejemplos"])
        lineas.append(f"  - {col}: {info['tipo']}   ejemplos: {ej}")
    return "\n".join(lineas)


def construir_bloque_schema(inventory_tbl: Table, transactions_tbl: Table) -> str:
    """Texto con el esquema de las dos tablas más notas de negocio, listo para el prompt."""
    notas = (
        "NOTAS:\n"
        "- inventory_tbl.price está en USD.\n"
        "- inventory_tbl.quantity_in_stock > 0 significa que hay stock.\n"
        "- inventory_tbl.name es el modelo (ej: 'Classic', 'Moon'); la forma del marco está en description.\n"
        "- transactions_tbl.timestamp es ISO-8601.\n"
        "- Una compra SUMA a la caja (amount positivo) y RESTA stock; una devolución al revés."
    )
    return (
        describir_tabla(inventory_tbl, "inventory_tbl")
        + "\n\n"
        + describir_tabla(transactions_tbl, "transactions_tbl")
        + "\n\n"
        + notas
    )


# ---------------------------------------------------------------------------
# Helpers disponibles para el código generado
# ---------------------------------------------------------------------------


def get_current_balance(transactions_tbl: Table, default: float = 0.0) -> float:
    """Saldo después de la última transacción registrada (o ``default`` si no hay ninguna)."""
    filas = transactions_tbl.all()
    if not filas:
        return default
    return float(filas[-1].get("balance_after_transaction", default))


def next_transaction_id(transactions_tbl: Table, prefijo: str = "TXN") -> str:
    """Siguiente id correlativo: TXN002, TXN003, ... según la cantidad de filas."""
    return f"{prefijo}{len(transactions_tbl) + 1:03d}"


if __name__ == "__main__":
    db, inv, txn = seed_db()
    print(construir_bloque_schema(inv, txn))
    print("saldo:", get_current_balance(txn), "próximo id:", next_transaction_id(txn))

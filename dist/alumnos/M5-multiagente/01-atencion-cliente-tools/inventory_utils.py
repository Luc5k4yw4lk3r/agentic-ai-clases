"""Datos iniciales de la tienda de anteojos de sol (lab 01, M5).

Dos DataFrames de pandas que hacen de "base de datos" en memoria:

- ``create_inventory_dataframe()``: 5 modelos de anteojos con stock y precio.
- ``create_transaction_dataframe()``: la caja, con una fila de saldo inicial.

Los valores de stock y precio salen de ``random`` con semilla fija (42), así que
son siempre los mismos: el modelo Mystique arranca con 3 unidades, que es lo que
hace fallar el caso "comprar 5 Mystique" del lab.

Nota de mantenimiento: el archivo original traía además funciones heredadas de
M3/M4 (ledger, ``update_stock``, ``execute_plan_with_reflection``...) que este lab
no usa. Se eliminaron para que el módulo sea legible de punta a punta.
"""
from __future__ import annotations

import random

import pandas as pd

NOMBRES = ["Aviator", "Wayfarer", "Mystique", "Sport", "Round"]
ITEM_IDS = ["SG001", "SG002", "SG003", "SG004", "SG005"]
DESCRIPCIONES = [
    "Diseñados originalmente para pilotos: lentes en forma de gota y marco metálico fino. "
    "Cobertura amplia y construcción liviana para uso prolongado.",
    "Marco grueso y angular que marca presencia. Combinan aire retro con un toque moderno; "
    "lentes rectangulares y acetato resistente.",
    "Inspirados en el glamour de los años 50: el marco se eleva en las puntas y dibuja una "
    "silueta elegante. Patillas con detalles.",
    "Pensados para deportes: una sola lente curva envolvente que protege del viento. "
    "Marco flexible y liviano con grips de goma.",
    "Lentes circulares en un marco minimalista. Un aire artístico y relajado que queda bien "
    "con todo.",
]


def create_inventory_dataframe() -> pd.DataFrame:
    """Crea el inventario inicial de la tienda.

    Returns:
        DataFrame con columnas name, item_id, description, quantity_in_stock, price.
        Con la semilla 42 el stock queda en [23, 6, 3, 11, 10] y el precio en
        [103, 92, 88, 144, 86].
    """
    random.seed(42)
    datos = {
        "name": NOMBRES,
        "item_id": ITEM_IDS,
        "description": DESCRIPCIONES,
        "quantity_in_stock": [random.randint(3, 25) for _ in range(5)],
        "price": [random.randint(75, 150) for _ in range(5)],
    }
    return pd.DataFrame(datos)


def create_transaction_dataframe(saldo_inicial: float = 500.00) -> pd.DataFrame:
    """Crea el registro de transacciones con una sola fila: el saldo de apertura de caja.

    Args:
        saldo_inicial: efectivo con el que abre la caja ese día.

    Returns:
        DataFrame con columnas transaction_id, customer_name, transaction_summary,
        transaction_amount, balance_after_transaction.
    """
    apertura = {
        "transaction_id": ["TXN001"],
        "customer_name": ["OPENING_BALANCE"],
        "transaction_summary": ["Saldo de apertura de caja"],
        "transaction_amount": [saldo_inicial],
        "balance_after_transaction": [saldo_inicial],
    }
    return pd.DataFrame(apertura)


if __name__ == "__main__":
    print(create_inventory_dataframe()[["name", "item_id", "quantity_in_stock", "price"]])
    print(create_transaction_dataframe())

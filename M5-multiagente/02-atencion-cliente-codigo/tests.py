"""Tests del lab 02 (M5): extracción y ejecución de código generado, sin API.

Correr: ``pytest -q`` dentro de esta carpeta.
Desde el notebook: ``from tests import run_all; run_all(extraer_bloque_ejecutable, ejecutar_codigo_generado)``.

Las dos funciones con hueco viven en el notebook. Con pytest se usan las versiones de
referencia de este archivo; ``run_all`` las reemplaza por las del alumno.
"""
from __future__ import annotations

import io
import re
import traceback
from contextlib import redirect_stdout
from datetime import datetime
from typing import Any, Callable

import pytest
from tinydb import Query, TinyDB
from tinydb.storages import MemoryStorage

import inv_utils
import utils

# ---------------------------------------------------------------------------
# Implementaciones de referencia (misma lógica que la solución del notebook)
# ---------------------------------------------------------------------------


def _extraer_referencia(texto: str) -> str:
    if not isinstance(texto, str) or not texto.strip():
        raise ValueError("La respuesta del modelo está vacía; se esperaba un bloque <execute_python>.")
    m = re.search(r"<execute_python>(.*?)</execute_python>", texto, re.DOTALL | re.IGNORECASE)
    if m is None:
        raise ValueError(f"La respuesta no trae un bloque <execute_python>...</execute_python>. Empieza así: {texto[:150]!r}")
    codigo = utils.quitar_fences(m.group(1))
    if not codigo:
        raise ValueError("El bloque <execute_python> está vacío.")
    return codigo


def _ejecutar_referencia(codigo: str, inventory_tbl, transactions_tbl, user_request: str = "") -> dict[str, Any]:
    namespace: dict[str, Any] = {
        "inventory_tbl": inventory_tbl, "transactions_tbl": transactions_tbl, "Query": Query,
        "get_current_balance": inv_utils.get_current_balance, "next_transaction_id": inv_utils.next_transaction_id,
        "datetime": datetime, "user_request": user_request,
    }
    buffer = io.StringIO()
    error = None
    try:
        with redirect_stdout(buffer):
            exec(codigo, namespace)
    except Exception:
        error = traceback.format_exc()
        print("El código generado falló al ejecutarse:\n" + error)
    return {"codigo": codigo, "stdout": buffer.getvalue().strip(), "error": error,
            "status": namespace.get("STATUS"), "answer_text": namespace.get("answer_text")}


EXTRAER: Callable = _extraer_referencia
EJECUTAR: Callable = _ejecutar_referencia


def tablas_en_memoria():
    """Base TinyDB en memoria con los datos iniciales (no toca data/store_db.json)."""
    db = TinyDB(storage=MemoryStorage)
    inv = db.table("inventory")
    txn = db.table("transactions")
    inv_utils.create_inventory(inv)
    inv_utils.create_transactions(txn)
    return inv, txn


@pytest.fixture
def tablas():
    return tablas_en_memoria()


# ---------------------------------------------------------------------------
# inv_utils y utils
# ---------------------------------------------------------------------------


def test_seed_en_memoria_tiene_6_productos_y_apertura():
    inv, txn = tablas_en_memoria()
    assert len(inv) == 6 and len(txn) == 1
    assert {r["name"]: r["quantity_in_stock"] for r in inv.all()} == {
        "Aviator": 23, "Wayfarer": 6, "Mystique": 3, "Sport": 11, "Classic": 10, "Moon": 10}
    assert inv_utils.get_current_balance(txn) == 500.0
    assert inv_utils.next_transaction_id(txn) == "TXN002"


def test_seed_db_en_archivo_temporal(tmp_path):
    db, inv, txn = inv_utils.seed_db(tmp_path / "store.json")
    assert (tmp_path / "store.json").exists() and len(inv) == 6
    db.close()


def test_schema_menciona_tablas_y_columnas():
    inv, txn = tablas_en_memoria()
    texto = inv_utils.construir_bloque_schema(inv, txn)
    for esperado in ("inventory_tbl", "transactions_tbl", "quantity_in_stock", "price", "balance_after_transaction", "NOTAS"):
        assert esperado in texto


def test_quitar_fences():
    assert utils.quitar_fences("```python\nx = 1\n```") == "x = 1"
    assert utils.quitar_fences("```\nx = 1\n```") == "x = 1"
    assert utils.quitar_fences("x = 1") == "x = 1"


# ---------------------------------------------------------------------------
# extraer_bloque_ejecutable
# ---------------------------------------------------------------------------


def test_extraer_bloque_simple():
    assert EXTRAER("texto\n<execute_python>\nSTATUS = 'ok'\n</execute_python>\nfin") == "STATUS = 'ok'"


def test_extraer_bloque_con_fences_y_mayusculas():
    assert EXTRAER("<EXECUTE_PYTHON>\n```python\nx = 1\n```\n</EXECUTE_PYTHON>") == "x = 1"


def test_extraer_bloque_multilinea_conserva_lineas():
    codigo = EXTRAER("<execute_python>\na = 1\n\nb = 2\n</execute_python>")
    assert codigo.splitlines() == ["a = 1", "", "b = 2"]


def test_extraer_sin_etiquetas_levanta_valueerror_en_espanol():
    with pytest.raises(ValueError, match="execute_python"):
        EXTRAER("Te explico: primero buscaría en la tabla y después...")
    with pytest.raises(ValueError):
        EXTRAER("")


# ---------------------------------------------------------------------------
# ejecutar_codigo_generado
# ---------------------------------------------------------------------------

CODIGO_LECTURA = '''
Item = Query()
res = inventory_tbl.search(Item.description.test(lambda d: "redondo" in d.lower()) & Item.price.test(lambda p, t: p < t, 100))
STATUS = "success" if res else "no_match"
answer_text = ", ".join(r["name"] for r in res)
print("LOG: ACTION=read")
'''

CODIGO_DEVOLUCION = '''
Item = Query()
item = inventory_tbl.get(Item.name == "Aviator")
amount = -item["price"] * 2
transactions_tbl.insert({"transaction_id": next_transaction_id(transactions_tbl), "customer_name": "C",
    "transaction_summary": "Devolución 2 Aviator", "transaction_amount": float(amount),
    "balance_after_transaction": get_current_balance(transactions_tbl) + amount, "timestamp": datetime.now().isoformat()})
inventory_tbl.update({"quantity_in_stock": item["quantity_in_stock"] + 2}, Item.item_id == item["item_id"])
STATUS = "success"
answer_text = "Listo."
'''


def test_ejecutar_lectura_devuelve_status_y_answer(tablas):
    inv, txn = tablas
    r = EJECUTAR(CODIGO_LECTURA, inv, txn, user_request="redondos baratos")
    assert r["error"] is None
    assert r["status"] == "success"
    assert r["answer_text"] == "Classic"           # Moon es redondo pero cuesta 120
    assert r["stdout"] == "LOG: ACTION=read"
    assert r["codigo"] == CODIGO_LECTURA
    assert len(txn) == 1                            # no mutó nada


def test_ejecutar_mutacion_toca_las_tablas(tablas):
    inv, txn = tablas
    r = EJECUTAR(CODIGO_DEVOLUCION, inv, txn)
    assert r["error"] is None and r["status"] == "success"
    assert inv.get(Query().name == "Aviator")["quantity_in_stock"] == 25
    filas = txn.all()
    assert len(filas) == 2 and filas[-1]["transaction_id"] == "TXN002"
    assert filas[-1]["transaction_amount"] == -160.0 and filas[-1]["balance_after_transaction"] == 340.0


def test_ejecutar_namespace_expone_lo_prometido(tablas):
    inv, txn = tablas
    codigo = ("nombres = sorted([inventory_tbl, transactions_tbl, Query, get_current_balance, next_transaction_id, datetime], key=str)\n"
              "STATUS = 'success'\nanswer_text = user_request")
    r = EJECUTAR(codigo, inv, txn, user_request="hola")
    assert r["error"] is None and r["answer_text"] == "hola"


def test_ejecutar_lambda_ve_variables_del_nivel_superior(tablas):
    """Con globals y locals separados (como en el original) esto daba NameError."""
    inv, txn = tablas
    codigo = "tope = 100\nItem = Query()\nres = inventory_tbl.search(Item.price.test(lambda p: p < tope))\nSTATUS = 'success'\nanswer_text = str(len(res))"
    r = EJECUTAR(codigo, inv, txn)
    assert r["error"] is None and r["answer_text"] == "4"


def test_ejecutar_error_devuelve_traceback_y_lo_muestra(tablas, capsys):
    inv, txn = tablas
    r = EJECUTAR("x = inventory_tbl.all()[0]['precio']", inv, txn)
    assert r["error"] is not None and "KeyError" in r["error"]
    assert r["status"] is None and r["answer_text"] is None
    assert "KeyError" in capsys.readouterr().out, "el traceback tiene que mostrarse, no solo guardarse"


def test_ejecutar_captura_stdout(tablas):
    inv, txn = tablas
    r = EJECUTAR("print('uno')\nprint('dos')\nSTATUS='success'\nanswer_text='x'", inv, txn)
    assert r["stdout"] == "uno\ndos"


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------


def run_all(extraer_bloque_ejecutable: Callable | None = None, ejecutar_codigo_generado: Callable | None = None) -> None:
    """Corre todos los tests con las funciones del alumno (si se pasan)."""
    global EXTRAER, EJECUTAR
    if extraer_bloque_ejecutable is not None:
        EXTRAER = extraer_bloque_ejecutable
    if ejecutar_codigo_generado is not None:
        EJECUTAR = ejecutar_codigo_generado

    class _Capsys:  # imitación mínima de capsys para test_ejecutar_error_devuelve_traceback_y_lo_muestra
        def __init__(self):
            self.buffer = io.StringIO()

        def readouterr(self):
            class R:
                out = self.buffer.getvalue()
            return R()

    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallas = 0
    for prueba in pruebas:
        params = prueba.__code__.co_varnames[: prueba.__code__.co_argcount]
        try:
            kwargs = {}
            if "tablas" in params:
                kwargs["tablas"] = tablas_en_memoria()
            if "tmp_path" in params:
                import tempfile
                from pathlib import Path
                kwargs["tmp_path"] = Path(tempfile.mkdtemp())
            if "capsys" in params:
                cap = _Capsys()
                with redirect_stdout(cap.buffer):
                    prueba(**kwargs, capsys=cap)
            else:
                prueba(**kwargs)
            print(f"OK    {prueba.__name__}")
        except AssertionError as e:
            fallas += 1
            print(f"FALLA {prueba.__name__}: {e}")
        except Exception as e:
            fallas += 1
            print(f"ERROR {prueba.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallas}/{len(pruebas)} tests pasaron.")

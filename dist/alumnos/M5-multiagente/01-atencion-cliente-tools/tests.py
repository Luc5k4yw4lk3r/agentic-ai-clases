"""Tests del lab 01 (M5): tools, resolución de referencias y executor. Ninguno llama a la API.

Correr: ``pytest -q`` dentro de esta carpeta.
Desde el notebook: ``from tests import run_all; run_all(ejecutar_plan)``.

El executor (``ejecutar_plan``) vive en el notebook, así que los tests que lo
necesitan lo reciben por parámetro vía ``run_all``; con pytest se usa una copia
de referencia definida acá (``_ejecutar_plan_referencia``) que replica la solución.
"""
from __future__ import annotations

import json
from typing import Any, Callable

import duckdb
import pandas as pd
import pytest

import inventory_utils
import tools
import utils

# ---------------------------------------------------------------------------
# Planes de prueba
# ---------------------------------------------------------------------------


def plan_operacion(producto: str, qty: int, devolucion: bool) -> dict[str, Any]:
    """Plan de 4 pasos (buscar, calcular, actualizar stock, registrar) para compra o devolución."""
    calc = "compute_refund" if devolucion else "compute_total"
    delta = qty if devolucion else -qty
    return {
        "reasoning": "plan de prueba",
        "steps": [
            {"step_number": 1, "description": f"Buscar {producto}",
             "tools": [{"use": "get_inventory_data", "args": {"product_name": producto}, "result_key": "prod"}],
             "validations": [{"name": "producto_encontrado", "use_tool": "assert_true", "args": {"value_from": "context.prod.item"}}]},
            {"step_number": 2, "description": "Calcular importe",
             "tools": [{"use": calc, "args": {"qty": qty, "price_from": "context.prod.item.price"}, "result_key": "monto"}],
             "validations": []},
            {"step_number": 3, "description": "Actualizar stock",
             "tools": [{"use": "update_inventory", "args": {"item_id_from": "context.prod.item.item_id", "delta": delta}, "result_key": "inv_after"}],
             "validations": [{"name": "stock_no_negativo", "use_tool": "assert_nonnegative_stock", "args": {"item_id_from": "context.prod.item.item_id"}}]},
            {"step_number": 4, "description": "Registrar en caja",
             "tools": [{"use": "append_transaction",
                        "args": {"customer_name": "CLIENTE_MOSTRADOR", "summary": "prueba", "amount_from": "context.monto.amount"},
                        "result_key": "txn"}],
             "validations": [{"name": "transaccion_creada", "use_tool": "assert_true", "args": {"value_from": "context.txn.transaction.transaction_id"}}]},
        ],
    }


# ---------------------------------------------------------------------------
# Executor de referencia (misma lógica que la solución del notebook)
# ---------------------------------------------------------------------------


def _crear_conexion(inventory_df, transaction_df):
    con = duckdb.connect()
    con.register("inventory_df", inventory_df)
    con.register("transaction_df", transaction_df)
    return con


def _validar_stock_no_negativo(ctx):
    inv = ctx["__frames__"]["inventory_df"]
    negativos = inv[inv["quantity_in_stock"] < 0]
    if negativos.empty:
        return {"name": "stock_no_negativo (executor)", "ok": True, "result": {"ok": True}}
    return {"name": "stock_no_negativo (executor)", "ok": False,
            "result": {"ok": False, "items": negativos[["item_id", "name", "quantity_in_stock"]].to_dict("records")}}


def _ejecutar_plan_referencia(plan, inventory_df, transaction_df, detener_en_fallo=True):
    con = _crear_conexion(inventory_df, transaction_df)
    ctx = {"__con__": con, "__frames__": {"inventory_df": inventory_df.copy(), "transaction_df": transaction_df.copy()}}
    reporte = {"ok": True, "steps": []}
    try:
        for paso in plan.get("steps", []):
            error_tool = None
            try:
                corridas = tools.run_tools_for_step(paso, ctx)
            except Exception as e:
                corridas = {}
                error_tool = f"{type(e).__name__}: {e}"
            validaciones = [tools.run_tool_validation(v, ctx) for v in paso.get("validations", [])]
            validaciones.append(_validar_stock_no_negativo(ctx))
            paso_ok = error_tool is None and all(v["ok"] for v in validaciones)
            if not paso_ok:
                reporte["ok"] = False
            reporte["steps"].append({"step_number": paso.get("step_number"), "description": paso.get("description", ""),
                                     "tools_run": list(corridas.keys()), "tool_error": error_tool,
                                     "validations": validaciones, "ok": paso_ok})
            if detener_en_fallo and not paso_ok:
                reporte["aborted"] = True
                reporte["abort_step"] = paso.get("step_number")
                reporte["abort_reason"] = error_tool or "validation_failed"
                break
    finally:
        con.close()
    reporte["updated_frames"] = {"inventory_df": ctx["__frames__"]["inventory_df"],
                                 "transaction_df": ctx["__frames__"]["transaction_df"]}
    return reporte


# El executor que se testea. pytest usa la referencia; run_all lo reemplaza por el del alumno.
EJECUTAR_PLAN: Callable = _ejecutar_plan_referencia


@pytest.fixture
def datos():
    return inventory_utils.create_inventory_dataframe(), inventory_utils.create_transaction_dataframe()


# ---------------------------------------------------------------------------
# Tests de datos y tools
# ---------------------------------------------------------------------------


def test_datos_iniciales_son_los_esperados():
    inv = inventory_utils.create_inventory_dataframe()
    assert list(inv["quantity_in_stock"]) == [23, 6, 3, 11, 10]
    assert list(inv["price"]) == [103, 92, 88, 144, 86]
    txn = inventory_utils.create_transaction_dataframe()
    assert len(txn) == 1 and txn["balance_after_transaction"].iloc[0] == 500.0


def test_catalogo_y_registro_coinciden():
    for nombre in tools.TOOL_REGISTRY:
        assert nombre in tools.CATALOGO_TOOLS, f"{nombre} está en el registro pero no en el catálogo"
    for nombre in tools.ARGS_OBLIGATORIOS:
        assert nombre in tools.TOOL_REGISTRY


def test_get_inventory_data_no_distingue_mayusculas():
    inv = inventory_utils.create_inventory_dataframe()
    con = _crear_conexion(inv, inventory_utils.create_transaction_dataframe())
    r = tools.get_inventory_data(con, product_name="aViAtOr")
    assert r["match_count"] == 1 and r["item"]["item_id"] == "SG001"
    assert tools.get_inventory_data(con, product_name="Inexistente")["item"] is None
    con.close()


def test_update_inventory_no_modifica_el_original():
    inv = inventory_utils.create_inventory_dataframe()
    r = tools.update_inventory(inv, "SG004", delta=-10)
    assert r["updated"]["quantity_in_stock"] == 1
    assert int(inv.loc[inv["item_id"] == "SG004", "quantity_in_stock"].iloc[0]) == 11


def test_update_inventory_errores_en_espanol():
    inv = inventory_utils.create_inventory_dataframe()
    with pytest.raises(ValueError, match="no existe"):
        tools.update_inventory(inv, "SG999", delta=1)
    with pytest.raises(ValueError, match="delta"):
        tools.update_inventory(inv, "SG001")


def test_append_transaction_recalcula_saldo_e_id():
    txn = inventory_utils.create_transaction_dataframe()
    r = tools.append_transaction(txn, "Ana", "compra", 150.0)
    assert r["transaction"]["transaction_id"] == "TXN002"
    assert r["transaction"]["balance_after_transaction"] == 650.0
    assert len(txn) == 1  # el original no cambió


def test_compute_refund_es_negativo():
    assert tools.compute_total(3, 100)["amount"] == 300.0
    assert tools.compute_refund(3, 100)["amount"] == -300.0


# ---------------------------------------------------------------------------
# Tests de referencias y canonización
# ---------------------------------------------------------------------------


def test_resolve_args_sigue_la_ruta_y_quita_from():
    ctx = {"prod": {"item": {"price": 144, "item_id": "SG004"}}}
    out = tools.resolve_args({"qty": 2, "price_from": "context.prod.item.price"}, ctx)
    assert out == {"qty": 2, "price": 144}


def test_resolve_args_ruta_inexistente_levanta_valueerror():
    ctx = {"prod": {"item": None}}
    with pytest.raises(ValueError, match="context.prod.item"):
        tools.resolve_args({"price_from": "context.prod.item.price"}, ctx)


def test_canonicalize_args_traduce_alias():
    assert tools.canonicalize_args("compute_total", {"quantity": 2, "unit_price": 10}) == {"qty": 2, "price": 10}
    assert tools.canonicalize_args("update_inventory", {"item_id": "x", "change": -1}) == {"item_id": "x", "delta": -1}
    assert tools.canonicalize_args("append_transaction", {"transaction_summary": "s"}) == {"summary": "s"}


def test_missing_required_detecta_faltantes():
    assert tools.missing_required("compute_total", {"qty": 1}) == ["price"]
    assert tools.missing_required("update_inventory", {"item_id": "x"}) == ["delta|quantity_new"]
    assert tools.missing_required("append_transaction", {"customer_name": "a", "summary": "b", "amount": 1}) == []


def test_run_tools_for_step_tool_desconocida():
    inv, txn = inventory_utils.create_inventory_dataframe(), inventory_utils.create_transaction_dataframe()
    con = _crear_conexion(inv, txn)
    ctx = {"__con__": con, "__frames__": {"inventory_df": inv, "transaction_df": txn}}
    with pytest.raises(ValueError, match="Tool desconocida"):
        tools.run_tools_for_step({"tools": [{"use": "lookup_product", "args": {}, "result_key": "x"}]}, ctx)
    con.close()


def test_run_tool_validation_nunca_levanta():
    inv, txn = inventory_utils.create_inventory_dataframe(), inventory_utils.create_transaction_dataframe()
    con = _crear_conexion(inv, txn)
    ctx = {"__con__": con, "__frames__": {"inventory_df": inv, "transaction_df": txn}}
    r = tools.run_tool_validation({"name": "v", "use_tool": "assert_gt", "args": {}}, ctx)
    assert r["ok"] is False and "tool_desconocida" in r["error"]
    r = tools.run_tool_validation({"name": "v", "use_tool": "assert_true", "args": {"value_from": "context.nada"}}, ctx)
    assert r["ok"] is False and "context.nada" in r["error"]
    con.close()


# ---------------------------------------------------------------------------
# Tests del executor
# ---------------------------------------------------------------------------


def test_executor_devolucion_pasa_y_no_toca_el_original(datos):
    inv, txn = datos
    rep = EJECUTAR_PLAN(plan_operacion("Aviator", 2, devolucion=True), inv, txn)
    assert rep["ok"] is True and len(rep["steps"]) == 4
    nuevo = rep["updated_frames"]["inventory_df"]
    assert int(nuevo.loc[nuevo["item_id"] == "SG001", "quantity_in_stock"].iloc[0]) == 25
    assert int(inv.loc[inv["item_id"] == "SG001", "quantity_in_stock"].iloc[0]) == 23
    nueva_txn = rep["updated_frames"]["transaction_df"]
    assert len(nueva_txn) == 2 and nueva_txn["transaction_amount"].iloc[-1] == -206.0
    assert len(txn) == 1


def test_executor_compra_grande_pasa(datos):
    inv, txn = datos
    rep = EJECUTAR_PLAN(plan_operacion("Sport", 10, devolucion=False), inv, txn)
    assert rep["ok"] is True
    nuevo = rep["updated_frames"]["inventory_df"]
    assert int(nuevo.loc[nuevo["item_id"] == "SG004", "quantity_in_stock"].iloc[0]) == 1
    assert rep["updated_frames"]["transaction_df"]["balance_after_transaction"].iloc[-1] == 500.0 + 1440.0


def test_executor_frena_por_stock_insuficiente(datos):
    inv, txn = datos
    rep = EJECUTAR_PLAN(plan_operacion("Mystique", 5, devolucion=False), inv, txn)
    assert rep["ok"] is False
    assert rep["aborted"] is True and rep["abort_step"] == 3
    assert len(rep["steps"]) == 3, "tiene que frenar en el paso 3: no se registra la transacción"
    assert len(rep["updated_frames"]["transaction_df"]) == 1
    fallidas = [v for v in rep["steps"][-1]["validations"] if not v["ok"]]
    assert fallidas, "el paso 3 tiene que tener al menos una validación fallida"


def test_executor_chequeo_fijo_aunque_el_plan_no_valide(datos):
    inv, txn = datos
    plan = plan_operacion("Mystique", 5, devolucion=False)
    for paso in plan["steps"]:
        paso["validations"] = []
    rep = EJECUTAR_PLAN(plan, inv, txn)
    assert rep["ok"] is False and rep["abort_step"] == 3


def test_executor_producto_inexistente(datos):
    inv, txn = datos
    rep = EJECUTAR_PLAN(plan_operacion("Inexistente", 1, devolucion=False), inv, txn)
    assert rep["ok"] is False and rep["abort_step"] == 1
    assert rep["steps"][0]["validations"][0]["ok"] is False


def test_executor_tool_desconocida_queda_en_el_reporte(datos):
    inv, txn = datos
    plan = {"steps": [{"step_number": 1, "description": "x",
                       "tools": [{"use": "assert_gt", "args": {}, "result_key": "r"}], "validations": []}]}
    rep = EJECUTAR_PLAN(plan, inv, txn)
    assert rep["ok"] is False
    assert "Tool desconocida" in rep["steps"][0]["tool_error"]
    assert rep["abort_reason"].startswith("ValueError")


def test_executor_sin_detener_sigue_hasta_el_final(datos):
    inv, txn = datos
    rep = EJECUTAR_PLAN(plan_operacion("Mystique", 5, devolucion=False), inv, txn, detener_en_fallo=False)
    assert rep["ok"] is False and len(rep["steps"]) == 4 and "aborted" not in rep


# ---------------------------------------------------------------------------
# Tests de utils
# ---------------------------------------------------------------------------


def test_parsear_json_repara_escapes():
    assert utils.parsear_json('{"a": 1}') == {"a": 1}
    assert utils.parsear_json('{"a": "it\\\'s $5"}') == {"a": "it's $5"}
    with pytest.raises(ValueError, match="JSON"):
        utils.parsear_json("esto no es json")
    with pytest.raises(ValueError, match="objeto"):
        utils.parsear_json("[1, 2]")


def test_resumen_reporte_es_legible(datos):
    inv, txn = datos
    rep = EJECUTAR_PLAN(plan_operacion("Mystique", 5, devolucion=False), inv, txn)
    texto = utils.resumen_reporte(rep)
    assert "FALLÓ" in texto and "Abortado en el paso 3" in texto


# ---------------------------------------------------------------------------
# run_all: para llamar desde el notebook con el executor del alumno
# ---------------------------------------------------------------------------


def run_all(ejecutar_plan: Callable | None = None) -> None:
    """Corre todos los tests. Si pasás tu ``ejecutar_plan``, los tests del executor usan el tuyo."""
    global EJECUTAR_PLAN
    if ejecutar_plan is not None:
        EJECUTAR_PLAN = ejecutar_plan
    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallas = 0
    for prueba in pruebas:
        try:
            if "datos" in prueba.__code__.co_varnames[: prueba.__code__.co_argcount]:
                prueba((inventory_utils.create_inventory_dataframe(), inventory_utils.create_transaction_dataframe()))
            else:
                prueba()
            print(f"OK    {prueba.__name__}")
        except AssertionError as e:
            fallas += 1
            print(f"FALLA {prueba.__name__}: {e}")
        except Exception as e:
            fallas += 1
            print(f"ERROR {prueba.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallas}/{len(pruebas)} tests pasaron.")

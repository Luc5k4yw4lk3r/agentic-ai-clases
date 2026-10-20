"""Catálogo de tools de la tienda y motor para correrlas desde un plan JSON (lab 01, M5).

Qué hay acá (todo viene dado; el alumno lo usa, no lo escribe):

1. **Tools**: funciones chicas que leen o modifican los dos DataFrames
   (``inventory_df`` y ``transaction_df``). Las de lectura usan DuckDB para hacer
   SQL sobre los DataFrames; las de escritura devuelven un DataFrame NUEVO (no
   modifican el que reciben).
2. **``TOOL_REGISTRY``**: diccionario nombre → función. El planner solo puede usar
   los nombres que están acá; cualquier otro nombre es un error.
3. **``CATALOGO_TOOLS``**: el mismo catálogo en texto, para pegarlo en el prompt
   del planner.
4. **Resolución de referencias**: un paso del plan puede usar un resultado de un
   paso anterior con la sintaxis ``"price_from": "context.prod.item.price"``.
   ``resolve_args`` convierte eso en ``"price": 103`` leyendo del contexto.
5. **``run_tools_for_step`` / ``run_tool_validation``**: corren las tools y las
   validaciones de un paso, inyectando la conexión y los DataFrames que la tool
   necesite.

Diferencias con el original: se quitaron los alias de tools (``lookup_product``,
``propose_transaction``, ``assert_gt``...) para que el catálogo que ve el modelo
y el registro sean exactamente el mismo; las tools levantan ``ValueError`` con
mensaje en español en vez de devolver ``{"error": ...}``; y una referencia
``context.x.y`` que no existe también levanta ``ValueError`` en vez de pasar
``None`` en silencio.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# 1. Tools de LECTURA (SQL sobre los DataFrames vía DuckDB)
# ---------------------------------------------------------------------------


def get_inventory_data(
    con: duckdb.DuckDBPyConnection,
    product_name: Optional[str] = None,
    item_id: Optional[str] = None,
) -> dict[str, Any]:
    """Busca en el inventario por nombre (sin distinguir mayúsculas) o por item_id.

    Returns:
        {"rows": DataFrame, "match_count": int, "item": dict | None}
        ``item`` es la fila como dict si hubo exactamente una coincidencia; si no, None.
    """
    if item_id:
        df = con.execute("SELECT * FROM inventory_df WHERE item_id = ?", [str(item_id)]).df()
    elif product_name:
        df = con.execute(
            "SELECT * FROM inventory_df WHERE lower(name) = lower(?)", [str(product_name)]
        ).df()
    else:
        df = con.execute("SELECT * FROM inventory_df").df()  # sin filtro: todo el catálogo
    item = df.iloc[0].to_dict() if len(df) == 1 else None
    return {"rows": df, "match_count": int(len(df)), "item": item}


def get_transaction_data(con: duckdb.DuckDBPyConnection, mode: str = "last_balance") -> dict[str, Any]:
    """Devuelve el último saldo de caja y el id de la última transacción."""
    if mode != "last_balance":
        raise ValueError(f"get_transaction_data: modo desconocido '{mode}'. El único soportado es 'last_balance'.")
    df = con.execute(
        "SELECT transaction_id, balance_after_transaction "
        "FROM transaction_df ORDER BY transaction_id DESC LIMIT 1"
    ).df()
    if df.empty:
        return {"mode": mode, "last_txn_id": None, "last_balance": 0.0}
    return {
        "mode": mode,
        "last_txn_id": str(df.iloc[0]["transaction_id"]),
        "last_balance": float(df.iloc[0]["balance_after_transaction"]),
    }


# ---------------------------------------------------------------------------
# 2. Tools de ESCRITURA (devuelven un DataFrame nuevo; no tocan el original)
# ---------------------------------------------------------------------------


def _siguiente_txn_id(df: pd.DataFrame, prefijo: str = "TXN") -> str:
    """TXN001, TXN002, ... según el número más alto que ya exista."""
    if df.empty:
        return f"{prefijo}001"
    numeros = []
    for valor in df["transaction_id"].astype(str):
        cola = re.findall(r"(\d+)$", valor)
        numeros.append(int(cola[0]) if cola else 0)
    return f"{prefijo}{max(numeros) + 1:03d}"


def update_inventory(
    inventory_df: pd.DataFrame,
    item_id: str,
    delta: Optional[int] = None,
    quantity_new: Optional[int] = None,
) -> dict[str, Any]:
    """Cambia el stock de un item: ``delta`` suma/resta, ``quantity_new`` fija el valor.

    Returns:
        {"inventory_df": DataFrame nuevo, "updated": {"item_id", "quantity_in_stock"}}
    """
    if delta is None and quantity_new is None:
        raise ValueError("update_inventory: hace falta 'delta' o 'quantity_new'.")
    inv = inventory_df.copy()
    mascara = inv["item_id"].astype(str) == str(item_id)
    if not mascara.any():
        raise ValueError(f"update_inventory: no existe el item_id '{item_id}'.")
    actual = int(inv.loc[mascara, "quantity_in_stock"].iloc[0])
    nuevo = int(quantity_new) if quantity_new is not None else actual + int(delta)
    inv.loc[mascara, "quantity_in_stock"] = nuevo
    return {"inventory_df": inv, "updated": {"item_id": str(item_id), "quantity_in_stock": nuevo}}


def append_transaction(
    transaction_df: pd.DataFrame,
    customer_name: str,
    summary: str,
    amount: float,
) -> dict[str, Any]:
    """Agrega una fila de transacción y recalcula el saldo a partir del último.

    Returns:
        {"transaction_df": DataFrame nuevo, "transaction": dict con la fila agregada}
    """
    salida = transaction_df.copy()
    ultimo_saldo = float(salida["balance_after_transaction"].iloc[-1]) if not salida.empty else 0.0
    fila = {
        "transaction_id": _siguiente_txn_id(salida),
        "customer_name": str(customer_name),
        "transaction_summary": str(summary),
        "transaction_amount": float(amount),
        "balance_after_transaction": ultimo_saldo + float(amount),
    }
    salida = pd.concat([salida, pd.DataFrame([fila])], ignore_index=True)
    return {"transaction_df": salida, "transaction": fila}


# ---------------------------------------------------------------------------
# 3. Helpers de cálculo y validaciones
# ---------------------------------------------------------------------------


def compute_total(qty: int, price: float) -> dict[str, Any]:
    """Importe de una compra (positivo)."""
    return {"amount": float(qty) * float(price)}


def compute_refund(qty: int, price: float) -> dict[str, Any]:
    """Importe de una devolución (negativo, porque sale plata de la caja)."""
    return {"amount": -float(qty) * float(price)}


def assert_true(value: Any) -> dict[str, Any]:
    """Pasa si ``value`` es "verdadero" (no None, no 0, no vacío)."""
    return {"ok": bool(value)}


def assert_nonnegative_stock(inventory_df: pd.DataFrame, item_id: str) -> dict[str, Any]:
    """Pasa si el stock del item es >= 0. Devuelve también la cantidad actual."""
    mascara = inventory_df["item_id"].astype(str) == str(item_id)
    if not mascara.any():
        return {"ok": False, "reason": "item_not_found"}
    cantidad = int(inventory_df.loc[mascara, "quantity_in_stock"].iloc[0])
    return {"ok": cantidad >= 0, "qty": cantidad}


# ---------------------------------------------------------------------------
# 4. Registro: nombre → función, args obligatorios, recursos compartidos
# ---------------------------------------------------------------------------

ToolFn = Callable[..., dict[str, Any]]

TOOL_REGISTRY: dict[str, ToolFn] = {
    "get_inventory_data": get_inventory_data,
    "get_transaction_data": get_transaction_data,
    "compute_total": compute_total,
    "compute_refund": compute_refund,
    "update_inventory": update_inventory,
    "append_transaction": append_transaction,
    "assert_true": assert_true,
    "assert_nonnegative_stock": assert_nonnegative_stock,
}

# Args que el plan tiene que traer sí o sí (el resto son opcionales o se inyectan).
ARGS_OBLIGATORIOS: dict[str, list[str]] = {
    "get_inventory_data": [],
    "get_transaction_data": [],
    "compute_total": ["qty", "price"],
    "compute_refund": ["qty", "price"],
    "update_inventory": ["item_id"],  # y además delta o quantity_new (ver missing_required)
    "append_transaction": ["customer_name", "summary", "amount"],
    "assert_true": ["value"],
    "assert_nonnegative_stock": ["item_id"],
}

# Recursos que el executor inyecta si el plan no los pasa: la conexión DuckDB y
# los DataFrames vigentes. Así el planner no tiene que saber cómo se accede a los datos.
RECURSOS_COMPARTIDOS: dict[str, list[str]] = {
    "get_inventory_data": ["con"],
    "get_transaction_data": ["con"],
    "update_inventory": ["inventory_df"],
    "append_transaction": ["transaction_df"],
    "assert_nonnegative_stock": ["inventory_df"],
}

CATALOGO_TOOLS = """\
1) get_inventory_data
   - args: { product_name?: string, item_id?: string }
   - devuelve: { rows: DataFrame, match_count: int, item: dict|null }
   - uso: buscar un producto por nombre (sin distinguir mayúsculas) o por item_id.
     item trae name, item_id, description, quantity_in_stock, price; es null si no hay
     exactamente una coincidencia.
2) get_transaction_data
   - args: { mode?: "last_balance" }
   - devuelve: { mode: string, last_txn_id: string|null, last_balance: number }
3) compute_total
   - args: { qty: number, price: number }
   - devuelve: { amount: number }          # positivo: entra plata a la caja
4) compute_refund
   - args: { qty: number, price: number }
   - devuelve: { amount: number }          # NEGATIVO: sale plata de la caja
5) update_inventory
   - args: { item_id: string, delta?: number, quantity_new?: number }
   - devuelve: { inventory_df: DataFrame, updated: { item_id: string, quantity_in_stock: number } }
   - uso: compra → delta = -cantidad; devolución → delta = +cantidad.
6) append_transaction
   - args: { customer_name: string, summary: string, amount: number }
   - devuelve: { transaction_df: DataFrame, transaction: { transaction_id, ... } }
7) assert_true                              # solo para "validations"
   - args: { value: any }                   # pasa si value no es null/0/vacío
   - devuelve: { ok: boolean }
8) assert_nonnegative_stock                 # solo para "validations"
   - args: { item_id: string }
   - devuelve: { ok: boolean, qty: number }
"""


def canonicalize_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Traduce nombres de args "casi correctos" a los canónicos del catálogo.

    El modelo a veces escribe ``quantity`` en vez de ``qty`` o ``unit_price`` en vez
    de ``price``. Acá los corregimos para no fallar por una diferencia de nombre.
    """
    a = dict(args or {})
    if tool_name == "get_inventory_data":
        for alternativa in ("name", "product", "query"):
            if "product_name" not in a and alternativa in a:
                a["product_name"] = a.pop(alternativa)
    if tool_name in ("compute_total", "compute_refund"):
        if "qty" not in a and "quantity" in a:
            a["qty"] = a.pop("quantity")
        if "price" not in a and "unit_price" in a:
            a["price"] = a.pop("unit_price")
        a.pop("sign", None)  # compute_refund ya devuelve negativo; un 'sign' extra se ignora
    if tool_name == "update_inventory":
        if "delta" not in a and "change" in a:
            a["delta"] = a.pop("change")
        for alternativa in ("new_quantity", "qty_new"):
            if "quantity_new" not in a and alternativa in a:
                a["quantity_new"] = a.pop(alternativa)
    if tool_name == "append_transaction":
        if "summary" not in a and "transaction_summary" in a:
            a["summary"] = a.pop("transaction_summary")
    return a


def missing_required(tool_name: str, args: dict[str, Any]) -> list[str]:
    """Lista de args obligatorios que faltan (o vinieron en None)."""
    faltan = [k for k in ARGS_OBLIGATORIOS.get(tool_name, []) if k not in args or args[k] is None]
    if tool_name == "update_inventory" and "delta" not in args and "quantity_new" not in args:
        faltan.append("delta|quantity_new")
    return faltan


# ---------------------------------------------------------------------------
# 5. Referencias al contexto: "context.prod.item.price"
# ---------------------------------------------------------------------------

_FALTA = object()  # centinela: distingue "la clave no existe" de "el valor es None"


def get_from_context(ctx: dict[str, Any], path: str) -> Any:
    """Sigue una ruta con puntos dentro del contexto.

    ``get_from_context(ctx, "context.prod.item.price")`` → ``ctx["prod"]["item"]["price"]``.
    Si una parte del camino no existe, levanta ValueError explicando cuál.
    """
    actual: Any = ctx
    recorrido = "context"
    for parte in path.split(".")[1:]:
        if isinstance(actual, dict) and parte in actual:
            actual = actual[parte]
            recorrido += "." + parte
        else:
            raise ValueError(
                f"La referencia '{path}' no se puede resolver: '{recorrido}' no tiene la clave "
                f"'{parte}'. ¿El paso anterior falló, usó otro result_key o devolvió null?"
            )
    return actual


def resolve_args(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Reemplaza referencias ``context.x.y`` por su valor y saca el sufijo ``_from``.

    Ejemplo: ``{"qty": 2, "price_from": "context.prod.item.price"}`` →
    ``{"qty": 2, "price": 103}``.
    """
    salida: dict[str, Any] = {}
    for clave, valor in (args or {}).items():
        clave_limpia = clave[: -len("_from")] if clave.endswith("_from") else clave
        if isinstance(valor, str) and valor.startswith("context."):
            salida[clave_limpia] = get_from_context(ctx, valor)
        else:
            salida[clave_limpia] = valor
    return salida


# ---------------------------------------------------------------------------
# 6. Correr las tools y validaciones de un paso
# ---------------------------------------------------------------------------


def _preparar_args(tool_name: str, raw_args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Resuelve referencias, canoniza nombres, chequea obligatorios e inyecta recursos."""
    args = resolve_args(raw_args, ctx)
    args = canonicalize_args(tool_name, args)
    faltan = missing_required(tool_name, args)
    if faltan:
        raise ValueError(
            f"A la tool '{tool_name}' le faltan args obligatorios: {faltan}. "
            f"Recibió: {sorted(args.keys())}."
        )
    for recurso in RECURSOS_COMPARTIDOS.get(tool_name, []):
        if recurso == "con":
            args.setdefault("con", ctx["__con__"])
        else:
            args.setdefault(recurso, ctx["__frames__"][recurso])
    return args


def run_tools_for_step(step: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Corre en orden las tools de un paso y guarda cada resultado en ``ctx[result_key]``.

    Si una tool devuelve un DataFrame actualizado (``inventory_df`` o
    ``transaction_df``), lo aplica al contexto y lo vuelve a registrar en DuckDB,
    así el siguiente paso ya ve el nuevo estado.

    Returns:
        dict result_key → resultado, solo de las tools de este paso.
    """
    resultados: dict[str, Any] = {}
    for spec in step.get("tools", []):
        nombre = spec.get("use")
        result_key = spec.get("result_key")
        if not nombre or not result_key:
            raise ValueError(f"Cada tool del plan necesita 'use' y 'result_key'. Recibí: {spec}")
        fn = TOOL_REGISTRY.get(nombre)
        if fn is None:
            raise ValueError(
                f"Tool desconocida: '{nombre}'. Las permitidas son: {sorted(TOOL_REGISTRY)}."
            )
        args = _preparar_args(nombre, spec.get("args", {}), ctx)
        resultado = fn(**args)

        # Auto-aplicar: si la tool devolvió un DataFrame nuevo, pasa a ser el vigente.
        for nombre_df in ("inventory_df", "transaction_df"):
            if isinstance(resultado, dict) and isinstance(resultado.get(nombre_df), pd.DataFrame):
                ctx["__frames__"][nombre_df] = resultado[nombre_df]
                ctx["__con__"].unregister(nombre_df)
                ctx["__con__"].register(nombre_df, resultado[nombre_df])

        ctx[result_key] = resultado
        resultados[result_key] = resultado
    return resultados


def run_tool_validation(validation: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Corre una validación del plan y devuelve ``{"name", "ok", "result" | "error"}``.

    A diferencia de las tools, una validación nunca levanta excepción: si algo
    está mal armado, devuelve ``ok: False`` con el motivo, para que el executor
    lo registre en el reporte.
    """
    nombre_val = validation.get("name", "validacion")
    tool_name = validation.get("use_tool")
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return {"name": nombre_val, "ok": False, "error": f"tool_desconocida:{tool_name}"}
    try:
        args = _preparar_args(tool_name, validation.get("args", {}), ctx)
        resultado = fn(**args)
    except ValueError as e:
        return {"name": nombre_val, "ok": False, "error": str(e)}
    return {"name": nombre_val, "ok": bool(resultado.get("ok", False)), "result": resultado}

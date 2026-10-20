# %% [markdown]
# # Atención al cliente con un plan de tools
# **Módulo 5 · Lab 01.** Un equipo de agentes (Planner → Reflector → Executor →
# Explicador) atiende pedidos de una tienda de anteojos de sol: el plan es un JSON
# que solo puede usar tools de un catálogo cerrado, y un executor determinístico lo
# corre con validaciones.
#
# ## Objetivos
# Al terminar vas a poder:
# - Explicar por qué separar *planificar* (LLM) de *ejecutar* (código) hace que un
#   agente sea auditable y seguro.
# - Escribir un planner que devuelve un plan en JSON usando `response_format={"type": "json_object"}`
#   y validar su estructura antes de usarlo.
# - Encadenar resultados entre pasos con referencias `"price_from": "context.prod.item.price"`.
# - Agregar un reflector que critica y corrige el plan, y un executor que frena cuando
#   una validación falla.
# - Convertir un reporte de ejecución fallido en una explicación legible para el cliente.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. (Repaso M4) En el lab de evaluaciones medimos la calidad de la *búsqueda web* sin
#    generar el ensayo completo. ¿Cómo se llama ese tipo de evaluación?
#    a) end-to-end  b) a nivel de componente  c) evaluación subjetiva con LLM como juez
# 2. (Repaso M4) La métrica "proporción de URLs que vienen de dominios preferidos" es:
#    a) subjetiva, sin ground truth  b) objetiva, con ground truth por ejemplo
#    c) imposible de calcular con código
# 3. (Nuevo) En este lab el plan que escribe el LLM **no puede contener SQL**: solo nombres
#    de tools de un catálogo. ¿Qué ganamos con esa restricción?
#    a) El modelo responde más rápido  b) Cada paso es auditable y solo puede hacer lo que
#    las tools permiten  c) No hace falta validar nada
# 4. (Nuevo) En un paso del plan aparece `"price_from": "context.prod.item.price"`. ¿Qué
#    significa?
#    a) El precio se busca en internet  b) El executor toma el valor que guardó un paso
#    anterior bajo `result_key: "prod"` y lo pasa como `price`  c) Es un comentario para el humano
# 5. (Base, pandas) Si hacés `inv2 = inventory_df.copy()` y después modificás `inv2`,
#    ¿cambia `inventory_df`?
#    a) Sí, siempre  b) No: `copy()` crea un DataFrame independiente  c) Solo si tiene más de 100 filas

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (evaluación a nivel de componente: aislás la búsqueda y la
# medís sola, más barato y con menos ruido), 2-b (hay una lista de dominios preferidos por
# ejemplo: es objetiva y se calcula con código), 3-b (el plan solo puede invocar lo que el
# catálogo permite; cada paso queda registrado y se puede revisar antes de ejecutar), 4-b
# (es una referencia al contexto que llena el executor; `resolve_args` la convierte en
# `price: 144`), 5-b (por eso en este lab el estado "real" solo cambia cuando vos reasignás
# `inventory_df = reporte["updated_frames"]["inventory_df"]`).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

import json
from typing import Any

import duckdb
import pandas as pd
from openai import OpenAI

import inventory_utils   # datos iniciales (dado)
import tools             # catálogo de tools + motor de ejecución (dado)
import utils             # print_html, parsear_json, resumen_reporte (dado)

client = OpenAI()

# %% [markdown]
# ## 1. La tienda: dos DataFrames que hacen de base de datos
#
# **Para qué.** Necesitamos un estado que los agentes puedan leer y modificar. Usamos dos
# DataFrames de pandas en memoria: el inventario y la caja (transacciones).
#
# **Por qué así.** Son chicos, se ven de un vistazo y se pueden copiar para probar
# planes sin romper nada. Después registramos los DataFrames en DuckDB para que las tools
# de lectura puedan hacer SQL sobre ellos.
#
# Los datos salen de `inventory_utils` con una semilla fija: el modelo **Mystique arranca
# con 3 unidades**. Acordate de ese número: es el que hace fallar uno de los pedidos.

# %%
inventory_df = inventory_utils.create_inventory_dataframe()
transaction_df = inventory_utils.create_transaction_dataframe()

utils.print_html(inventory_df[["name", "item_id", "quantity_in_stock", "price"]], title="Inventario inicial")
utils.print_html(transaction_df, title="Caja inicial")

# %% [markdown]
# ### 1.1 DuckDB sobre pandas
# `duckdb.connect()` crea una base en memoria; `con.register("inventory_df", df)` hace que
# la tabla `inventory_df` apunte al DataFrame. Las tools de lectura usan esta conexión.

# %%
def crear_conexion(inventory_df: pd.DataFrame, transaction_df: pd.DataFrame) -> duckdb.DuckDBPyConnection:
    """Abre una conexión DuckDB en memoria con los dos DataFrames registrados como tablas."""
    con = duckdb.connect()
    con.register("inventory_df", inventory_df)
    con.register("transaction_df", transaction_df)
    return con


con = crear_conexion(inventory_df, transaction_df)
utils.print_html(con.sql("SELECT name, quantity_in_stock, price FROM inventory_df WHERE price < 100").df(),
                 title="SQL sobre el DataFrame: modelos de menos de $100")

# %% [markdown]
# ## 2. El catálogo de tools
#
# **Para qué.** Un LLM no puede tocar un DataFrame: necesita funciones que lo hagan por él.
# `tools.py` trae ocho, divididas en:
#
# | Tipo | Tools | Qué hacen |
# |---|---|---|
# | Lectura | `get_inventory_data`, `get_transaction_data` | SQL sobre los DataFrames vía DuckDB |
# | Cálculo | `compute_total`, `compute_refund` | importe de una compra (positivo) o devolución (negativo) |
# | Escritura | `update_inventory`, `append_transaction` | devuelven un DataFrame **nuevo** con el cambio |
# | Validación | `assert_true`, `assert_nonnegative_stock` | devuelven `{"ok": bool}` |
#
# **Por qué así.** Las tools de escritura no modifican el DataFrame que reciben: devuelven
# uno nuevo. El executor decide si lo adopta. Eso es lo que permite "probar" un plan sin
# comprometer el estado.
#
# `tools.CATALOGO_TOOLS` es el mismo catálogo en texto: es lo que va a leer el planner.

# %%
print(tools.CATALOGO_TOOLS)

# %%
# Probamos dos tools a mano, como lo haría el executor
prod = tools.TOOL_REGISTRY["get_inventory_data"](con=con, product_name="aviator")   # sin distinguir mayúsculas
utils.print_html(prod["item"], title="get_inventory_data → item")

total = tools.TOOL_REGISTRY["compute_total"](qty=3, price=prod["item"]["price"])
utils.print_html(total, title="compute_total(qty=3, price=...)")

# %% [markdown]
# ## 3. Anatomía de un plan
#
# Un plan es un dict con `reasoning` y una lista `steps`. Cada paso tiene:
#
# ```json
# {
#   "step_number": 2,
#   "description": "Calcular el reintegro de 2 unidades",
#   "tools": [
#     {"use": "compute_refund", "args": {"qty": 2, "price_from": "context.prod.item.price"}, "result_key": "refund"}
#   ],
#   "validations": []
# }
# ```
#
# - `use`: nombre de una tool del catálogo. Nada más.
# - `result_key`: con qué nombre se guarda el resultado en el **contexto** (`ctx`), un dict
#   que vive durante toda la ejecución.
# - `*_from`: cualquier arg que termine en `_from` y cuyo valor empiece con `context.` es
#   una **referencia** a algo que calculó un paso anterior.
#
# ### 3.1 Cómo se resuelve `"price_from": "context.prod.item.price"`
#
# ```text
# ctx después del paso 1 (result_key = "prod"):
#
#   ctx
#   └── "prod" ──► {"rows": <DataFrame 1 fila>,
#                   "match_count": 1,
#                   "item": {"name": "Sport", "item_id": "SG004",
#                            "quantity_in_stock": 11, "price": 144}}
#
# paso 2 pide:  {"qty": 2, "price_from": "context.prod.item.price"}
#                                         │
#   resolve_args sigue la ruta ───────────┘   context → prod → item → price  = 144
#   y saca el sufijo "_from":                 {"qty": 2, "price": 144}
#
#   compute_refund(qty=2, price=144)  →  {"amount": -288.0}
#
#   ctx
#   ├── "prod"   ──► {...}
#   └── "refund" ──► {"amount": -288.0}        ← disponible para el paso 3 como context.refund.amount
# ```
#
# Si la ruta no existe (por ejemplo `item` es `null` porque el producto no se encontró),
# `resolve_args` levanta un `ValueError` que dice exactamente qué parte falló.

# %%
# Lo vemos con código: un contexto de juguete y resolve_args
ctx_juguete = {"prod": {"item": {"name": "Sport", "item_id": "SG004", "price": 144}}}
print(tools.resolve_args({"qty": 2, "price_from": "context.prod.item.price"}, ctx_juguete))

try:
    tools.resolve_args({"price_from": "context.prod.item.precio"}, ctx_juguete)   # clave mal escrita
except ValueError as e:
    print("ValueError:", e)

# %% [markdown]
# ### 3.2 Ejemplo resuelto: un plan escrito a mano
# Este plan devuelve 2 anteojos Sport. Lo vamos a usar dos veces: ahora, para ver cómo se
# ejecuta, y después como ejemplo dentro del prompt del planner (few-shot).

# %%
EJEMPLO_PLAN = {
    "reasoning": "El cliente devuelve 2 Sport: buscar el producto, calcular el reintegro (negativo), "
                 "sumar 2 al stock y registrar la transacción.",
    "steps": [
        {
            "step_number": 1,
            "description": "Buscar el producto 'Sport' y guardar sus datos",
            "tools": [
                {"use": "get_inventory_data", "args": {"product_name": "Sport"}, "result_key": "prod"}
            ],
            "validations": [
                {"name": "producto_encontrado", "use_tool": "assert_true", "args": {"value_from": "context.prod.item"}}
            ],
        },
        {
            "step_number": 2,
            "description": "Calcular el reintegro de 2 unidades",
            "tools": [
                {"use": "compute_refund", "args": {"qty": 2, "price_from": "context.prod.item.price"}, "result_key": "refund"}
            ],
            "validations": [],
        },
        {
            "step_number": 3,
            "description": "Sumar las 2 unidades devueltas al stock",
            "tools": [
                {"use": "update_inventory", "args": {"item_id_from": "context.prod.item.item_id", "delta": 2}, "result_key": "inv_after"}
            ],
            "validations": [
                {"name": "stock_no_negativo", "use_tool": "assert_nonnegative_stock",
                 "args": {"item_id_from": "context.prod.item.item_id"}}
            ],
        },
        {
            "step_number": 4,
            "description": "Registrar la devolución en la caja",
            "tools": [
                {"use": "append_transaction",
                 "args": {"customer_name": "CLIENTE_MOSTRADOR", "summary": "Devolución de 2 anteojos Sport",
                          "amount_from": "context.refund.amount"},
                 "result_key": "txn"}
            ],
            "validations": [
                {"name": "transaccion_creada", "use_tool": "assert_true",
                 "args": {"value_from": "context.txn.transaction.transaction_id"}}
            ],
        },
    ],
}

# %% [markdown]
# ## 4. El executor
#
# **Para qué.** Recorre los pasos del plan en orden, corre las tools, corre las
# validaciones y arma un **reporte**. Si algo falla, frena.
#
# **Por qué así.** El executor es código común, sin LLM. Es la parte del sistema en la que
# confiamos: el modelo *propone*, el executor *dispone*. Por eso además de las validaciones
# que trae el plan, el executor tiene **un chequeo propio que no se negocia**: ningún item
# puede quedar con stock negativo. Si el planner se olvida de pedir esa validación, el
# executor la hace igual.
#
# **Importante:** el executor trabaja sobre **copias** de los DataFrames. Devuelve las
# versiones nuevas en `reporte["updated_frames"]`, pero el estado "real" de la tienda solo
# cambia si vos hacés `inventory_df = reporte["updated_frames"]["inventory_df"]`.

# %%
def validar_stock_no_negativo(ctx: dict[str, Any]) -> dict[str, Any]:
    """Chequeo fijo del executor: ningún item del inventario vigente puede tener stock < 0.

    Devuelve el mismo formato que una validación del plan: {"name", "ok", "result"}.
    """
    inv = ctx["__frames__"]["inventory_df"]
    negativos = inv[inv["quantity_in_stock"] < 0]
    if negativos.empty:
        return {"name": "stock_no_negativo (executor)", "ok": True, "result": {"ok": True}}
    detalle = negativos[["item_id", "name", "quantity_in_stock"]].to_dict("records")
    return {"name": "stock_no_negativo (executor)", "ok": False, "result": {"ok": False, "items": detalle}}


def ejecutar_plan(
    plan: dict[str, Any],
    inventory_df: pd.DataFrame,
    transaction_df: pd.DataFrame,
    detener_en_fallo: bool = True,
) -> dict[str, Any]:
    """Ejecuta un plan de tools paso a paso y devuelve un reporte.

    El reporte tiene: ok (bool), steps (lista con un dict por paso ejecutado),
    aborted / abort_step / abort_reason si frenó antes de terminar, y
    updated_frames con los DataFrames resultantes (copias; el original no se toca).
    """
    con = crear_conexion(inventory_df, transaction_df)
    ctx: dict[str, Any] = {
        "__con__": con,
        "__frames__": {"inventory_df": inventory_df.copy(), "transaction_df": transaction_df.copy()},
    }
    reporte: dict[str, Any] = {"ok": True, "steps": []}
    try:
        for paso in plan.get("steps", []):
            numero = paso.get("step_number")
            descripcion = paso.get("description", "")

            # Paso 1 (dado): correr las tools del paso. Si una explota, lo anotamos y seguimos
            # a las validaciones para que quede registrado en el reporte.
            error_tool = None
            try:
                corridas = tools.run_tools_for_step(paso, ctx)
            except Exception as e:
                corridas = {}
                error_tool = f"{type(e).__name__}: {e}"

            # Paso 2: correr las validaciones que pide el plan (tools.run_tool_validation),
            # agregar el chequeo fijo de stock del executor, y decidir paso_ok:
            # el paso pasa solo si no hubo error de tool y TODAS las validaciones dieron ok.
            ### BEGIN SOLUTION
            ### STUDENT: validaciones = []   # Pista: un for sobre paso.get("validations", [])
            ### STUDENT: raise NotImplementedError("Completá: validaciones del plan + validar_stock_no_negativo(ctx) + paso_ok")
            validaciones = []
            for v in paso.get("validations", []):
                validaciones.append(tools.run_tool_validation(v, ctx))
            validaciones.append(validar_stock_no_negativo(ctx))
            paso_ok = error_tool is None and all(v["ok"] for v in validaciones)
            ### END SOLUTION

            # Paso 3 (dado): registrar el paso y frenar si corresponde.
            if not paso_ok:
                reporte["ok"] = False
            reporte["steps"].append({
                "step_number": numero,
                "description": descripcion,
                "tools_run": list(corridas.keys()),
                "tool_error": error_tool,
                "validations": validaciones,
                "ok": paso_ok,
            })
            if detener_en_fallo and not paso_ok:
                reporte["aborted"] = True
                reporte["abort_step"] = numero
                reporte["abort_reason"] = error_tool or "validation_failed"
                break
    finally:
        con.close()

    reporte["updated_frames"] = {
        "inventory_df": ctx["__frames__"]["inventory_df"],
        "transaction_df": ctx["__frames__"]["transaction_df"],
    }
    return reporte

# %%
# Prueba rápida: el plan de ejemplo (devolver 2 Sport) sobre el estado actual
reporte = ejecutar_plan(EJEMPLO_PLAN, inventory_df, transaction_df)
print(utils.resumen_reporte(reporte))

utils.print_html(reporte["updated_frames"]["inventory_df"][["name", "quantity_in_stock"]], title="Inventario en el reporte (Sport pasó de 11 a 13)")
utils.print_html(inventory_df[["name", "quantity_in_stock"]], title="inventory_df original: sigue en 11 (no lo reasignamos)")

# %%
# Y un plan que tiene que fallar: vender 5 Mystique cuando hay 3.
# Fijate que este plan NO pide la validación de stock: el chequeo fijo del executor lo frena igual.
PLAN_MYSTIQUE_SIN_VALIDAR = {
    "reasoning": "Vender 5 Mystique (plan incompleto a propósito).",
    "steps": [
        {"step_number": 1, "description": "Buscar Mystique",
         "tools": [{"use": "get_inventory_data", "args": {"product_name": "Mystique"}, "result_key": "prod"}],
         "validations": []},
        {"step_number": 2, "description": "Descontar 5 del stock",
         "tools": [{"use": "update_inventory", "args": {"item_id_from": "context.prod.item.item_id", "delta": -5}, "result_key": "inv_after"}],
         "validations": []},
        {"step_number": 3, "description": "Registrar la venta",
         "tools": [{"use": "append_transaction", "args": {"customer_name": "CLIENTE_MOSTRADOR", "summary": "Venta 5 Mystique", "amount": 440}, "result_key": "txn"}],
         "validations": []},
    ],
}
reporte_fallido = ejecutar_plan(PLAN_MYSTIQUE_SIN_VALIDAR, inventory_df, transaction_df)
print(utils.resumen_reporte(reporte_fallido))
assert reporte_fallido["ok"] is False and reporte_fallido["abort_step"] == 2

# %% [markdown]
# ## 5. Los agentes
#
# Hasta acá el plan lo escribimos nosotros. Ahora entran los LLMs, cada uno con un rol:
#
# ```text
# pedido ──► Planner ──► borrador ──► Reflector ──► plan final ──► Executor ──► reporte
#            (CHEAP)                  (STRONG)                     (código)       │
#                                                                        ok? ─no─► Explicador ──► texto
# ```
#
# ### 5.1 Planner
#
# **Para qué.** Convierte el pedido del cliente ("quiero devolver dos Aviator") en un plan
# con la estructura de la sección 3.
#
# **Por qué así.** Le damos el catálogo de tools, reglas estrictas y un ejemplo completo
# (`EJEMPLO_PLAN`). Pedimos `response_format={"type": "json_object"}` para que la respuesta
# sea JSON válido sí o sí; aun así validamos que `steps` sea una lista, porque "JSON
# válido" no significa "con la forma que yo quería".
#
# El prompt está en español porque ustedes lo tienen que poder leer y modificar.

# %%
REGLAS_PLANNER = """\
Sos el sistema de planificación de una tienda de anteojos de sol. Tu trabajo es convertir el
pedido de un cliente en un PLAN COMPLETO que se ejecuta de forma automática usando SOLO TOOLS.

Datos (dos tablas en memoria):
- inventory_df(name, item_id, description, quantity_in_stock, price)
- transaction_df(transaction_id, customer_name, transaction_summary, transaction_amount, balance_after_transaction)

Pedidos posibles: compra ("quiero comprar 3 Aviator"), devolución ("devuelvo dos Sport"),
consulta ("¿tienen Mystique?"), recorrida ("¿qué hay disponible?").

TOOLS PERMITIDAS (no inventes otras; usá los nombres de args exactamente así):
<<CATALOGO>>

REGLAS ESTRICTAS:
1) Respondé SOLO con un JSON válido con las claves "reasoning" (texto) y "steps" (lista).
2) Cada paso tiene: "step_number" (entero), "description" (texto corto), "tools" (lista de
   {"use": nombre, "args": {...}, "result_key": nombre_en_contexto}) y "validations" (lista de
   {"name": ..., "use_tool": "assert_true" | "assert_nonnegative_stock", "args": {...}}).
3) Para usar un resultado anterior, escribí el arg con sufijo "_from" y una ruta que empiece con
   "context.", por ejemplo {"price_from": "context.prod.item.price"}.
4) Nada de SQL en el plan: las tools hacen el SQL por dentro.
5) Compra o devolución siempre incluyen, en este orden: get_inventory_data (con validación
   producto_encontrado), compute_total (compra) o compute_refund (devolución), update_inventory
   (delta negativo para compra, positivo para devolución, con validación assert_nonnegative_stock)
   y append_transaction (amount tomado del contexto; el "summary" lo escribís vos, en español).
6) Si el pedido no dice el nombre del cliente, usá "CLIENTE_MOSTRADOR".

EJEMPLO COMPLETO (pedido: "devuelvo 2 anteojos Sport"):
<<EJEMPLO>>
"""


def especificacion_planner(catalogo: str) -> str:
    """Arma el texto de la especificación insertando el catálogo de tools y el plan de ejemplo."""
    ejemplo = json.dumps(EJEMPLO_PLAN, indent=2, ensure_ascii=False)
    return REGLAS_PLANNER.replace("<<CATALOGO>>", catalogo).replace("<<EJEMPLO>>", ejemplo)


print(especificacion_planner(tools.CATALOGO_TOOLS)[:1200], "\n[...]")

# %%
def generar_plan(pedido: str, catalogo: str, model: str = MODEL_CHEAP) -> dict[str, Any]:
    """Planner: convierte el pedido del cliente en un plan JSON que solo usa tools del catálogo.

    Args:
        pedido: lo que dijo el cliente, en lenguaje natural.
        catalogo: texto con las tools permitidas (normalmente tools.CATALOGO_TOOLS).
        model: modelo a usar (barato: es generación).

    Returns:
        dict con "reasoning" y "steps" (lista de pasos).
    """
    # Paso 1: armar los mensajes (system: "respondé solo JSON según la especificación";
    # user: especificacion_planner(catalogo) + el pedido) y llamar al modelo con
    # response_format={"type": "json_object"}.
    ### BEGIN SOLUTION
    especificacion = especificacion_planner(catalogo)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Respondé únicamente con JSON que cumpla la especificación de planificación."},
            {"role": "user", "content": f"{especificacion}\n\nPedido del cliente: {pedido}\nEscribí el plan ahora."},
        ],
        response_format={"type": "json_object"},
    )
    contenido = response.choices[0].message.content
    ### END SOLUTION

    # Paso 2: convertir el texto en dict con utils.parsear_json y validar que tenga una
    # clave "steps" que sea una lista no vacía; si no, levantar ValueError explicando qué vino.
    ### BEGIN SOLUTION
    plan = utils.parsear_json(contenido)
    if not isinstance(plan.get("steps"), list) or len(plan["steps"]) == 0:
        raise ValueError(
            f"El planner devolvió un JSON sin una lista 'steps' válida. Claves recibidas: {sorted(plan.keys())}"
        )
    ### END SOLUTION
    return plan

# %%
# Prueba rápida del planner
pedido = "Quiero devolver dos anteojos Aviator"
borrador = generar_plan(pedido, tools.CATALOGO_TOOLS)
print("Pasos:", len(borrador["steps"]))
for paso in borrador["steps"]:
    print(f"  {paso['step_number']}. {paso['description']}  →  {[t['use'] for t in paso['tools']]}")

# %% [markdown]
# ### 5.2 Reflector
#
# **Para qué.** El borrador del planner puede traer errores chicos: un arg con nombre
# equivocado, una validación que falta, una tool inventada. El reflector lo revisa contra la
# misma especificación y devuelve una **crítica** y un **plan revisado**.
#
# **Por qué así.** Es el patrón de reflexión de M2 aplicado a un plan en vez de a un texto.
# Usamos el modelo fuerte: criticar bien es más difícil que generar. Si el revisor devuelve
# algo roto, nos quedamos con el borrador y lo avisamos (nunca en silencio).

# %%
def reflexionar_plan(pedido: str, plan: dict[str, Any], model: str = MODEL_STRONG) -> dict[str, Any]:
    """Reflector: critica el borrador contra la especificación y devuelve un plan corregido.

    Returns:
        dict con "critica" (str) y "plan_revisado" (dict con "steps").
        Si el modelo no devuelve un plan_revisado válido, se devuelve el borrador original
        y la crítica lo dice.
    """
    # Paso 1: llamar al modelo (json_object) con un system de "revisor senior de planes" que
    # pida un JSON con las claves "critica" y "plan_revisado", y un user con la
    # especificación, el pedido y el borrador (json.dumps).
    ### BEGIN SOLUTION
    especificacion = especificacion_planner(tools.CATALOGO_TOOLS)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "Sos un revisor senior de planes. Respondé SOLO con un JSON con dos claves: "
                "'critica' (texto en español con los problemas que encontraste, o 'sin observaciones') "
                "y 'plan_revisado' (el plan corregido, con la misma estructura que el borrador)."
            )},
            {"role": "user", "content": (
                f"ESPECIFICACIÓN QUE EL PLAN DEBE CUMPLIR:\n{especificacion}\n\n"
                f"PEDIDO DEL CLIENTE:\n{pedido}\n\n"
                f"BORRADOR DEL PLAN (JSON):\n{json.dumps(plan, ensure_ascii=False)}\n\n"
                "Revisá: nombres de tools y de args exactos, referencias context.* correctas, "
                "validaciones de producto_encontrado y de stock presentes, signo del importe. "
                "Devolvé la crítica y el plan corregido."
            )},
        ],
        response_format={"type": "json_object"},
    )
    contenido = response.choices[0].message.content
    ### END SOLUTION

    # Paso 2: parsear con utils.parsear_json. Si "plan_revisado" no es un dict con una lista
    # "steps", avisar con print y devolver el borrador original como plan_revisado.
    ### BEGIN SOLUTION
    datos = utils.parsear_json(contenido)
    plan_revisado = datos.get("plan_revisado")
    if not isinstance(plan_revisado, dict) or not isinstance(plan_revisado.get("steps"), list):
        print("AVISO: el reflector no devolvió un 'plan_revisado' con 'steps'; se usa el borrador.")
        return {"critica": "El revisor no devolvió un plan válido; se mantiene el borrador.", "plan_revisado": plan}
    resultado = {"critica": str(datos.get("critica", "(sin crítica)")), "plan_revisado": plan_revisado}
    ### END SOLUTION
    return resultado

# %%
# Prueba rápida: un borrador con dos errores a propósito (arg "quantity" en vez de "qty"
# y sin validación de producto_encontrado). ¿El reflector los ve?
BORRADOR_CON_ERRORES = {
    "reasoning": "Comprar 2 Aviator.",
    "steps": [
        {"step_number": 1, "description": "Buscar Aviator",
         "tools": [{"use": "get_inventory_data", "args": {"product_name": "Aviator"}, "result_key": "prod"}],
         "validations": []},
        {"step_number": 2, "description": "Calcular total",
         "tools": [{"use": "compute_total", "args": {"quantity": 2, "price_from": "context.prod.item.price"}, "result_key": "total"}],
         "validations": []},
    ],
}
reflexion = reflexionar_plan("Quiero comprar 2 anteojos Aviator", BORRADOR_CON_ERRORES)
print("CRÍTICA:\n", reflexion["critica"])
print("\nPasos del plan revisado:", len(reflexion["plan_revisado"]["steps"]))

# %% [markdown]
# ### 5.3 Explicador de errores
#
# **Para qué.** Cuando el executor frena, el reporte es técnico (`abort_step: 2`,
# `qty: -2`). El cliente y el vendedor necesitan una frase: "no alcanza el stock, hay 3;
# ¿querés llevar 3?".
#
# **Por qué así.** Es la tarea más fácil del pipeline (resumir un JSON), así que alcanza
# con el modelo barato. Antes de mandar el reporte al modelo le sacamos `updated_frames`
# (son DataFrames, no aportan y ocupan tokens).

# %%
def explicar_error(pedido: str, reporte: dict[str, Any], model: str = MODEL_CHEAP) -> str:
    """Explicador: traduce un reporte de ejecución fallido a 2 o 3 frases para el vendedor.

    Returns:
        texto en español con qué falló y qué se puede hacer.
    """
    reporte_liviano = {k: v for k, v in reporte.items() if k != "updated_frames"}
    # Único paso: llamar al modelo (texto normal, sin json_object) con el pedido y el reporte
    # (json.dumps con default=str para que no falle si hay valores raros) y devolver el contenido.
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "Sos el encargado de una tienda de anteojos. Te paso el pedido de un cliente y el reporte "
                "técnico de por qué no se pudo completar. Explicá en 2 o 3 frases, en español simple y sin "
                "jerga, qué pasó y qué alternativa le ofrecerías al cliente."
            )},
            {"role": "user", "content": (
                f"Pedido del cliente:\n{pedido}\n\n"
                f"Reporte de ejecución (JSON):\n{json.dumps(reporte_liviano, ensure_ascii=False, default=str)}"
            )},
        ],
    )
    texto = response.choices[0].message.content
    ### END SOLUTION
    return texto

# %%
# Prueba rápida con el reporte fallido de la sección 4
print(explicar_error("Quiero comprar 5 anteojos Mystique", reporte_fallido))

# %% [markdown]
# ## 6. Todo junto: atender un pedido de punta a punta
#
# `atender_pedido` encadena los cuatro roles. Fijate que el estado de la tienda **no se
# toca adentro**: la función devuelve el reporte y vos decidís si adoptás los DataFrames
# nuevos. Esa decisión queda a la vista en la celda, no escondida en una función.

# %%
def atender_pedido(pedido: str, inventory_df: pd.DataFrame, transaction_df: pd.DataFrame) -> dict[str, Any]:
    """Planner → Reflector → Executor (→ Explicador si falló). Devuelve el reporte del executor."""
    utils.print_html(pedido, title="Pedido")

    borrador = generar_plan(pedido, tools.CATALOGO_TOOLS)
    reflexion = reflexionar_plan(pedido, borrador)
    plan_final = reflexion["plan_revisado"]
    utils.print_html(reflexion["critica"], title="Crítica del reflector")
    utils.print_html(plan_final, title="Plan final")

    reporte = ejecutar_plan(plan_final, inventory_df, transaction_df)
    utils.print_html(utils.resumen_reporte(reporte), title="Reporte de ejecución")

    if not reporte["ok"]:
        utils.print_html(explicar_error(pedido, reporte), title="Explicación para el cliente")
    return reporte

# %%
# Caso 1: tiene que FALLAR (hay 3 Mystique)
reporte = atender_pedido("Quiero comprar cinco anteojos Mystique", inventory_df, transaction_df)
assert reporte["ok"] is False, "Este pedido tenía que fallar por falta de stock"

# %%
# Caso 2: devolución, tiene que pasar. Si pasó, ADOPTAMOS el nuevo estado.
reporte = atender_pedido("Quiero devolver dos anteojos Aviator", inventory_df, transaction_df)
if reporte["ok"]:
    inventory_df = reporte["updated_frames"]["inventory_df"]
    transaction_df = reporte["updated_frames"]["transaction_df"]
utils.print_html(inventory_df[["name", "quantity_in_stock"]], title="Inventario después (Aviator: 23 → 25)")
utils.print_html(transaction_df, title="Caja después")

# %%
# Caso 3: compra grande, tiene que pasar (hay 11 Sport)
reporte = atender_pedido("Quiero comprar diez anteojos Sport", inventory_df, transaction_df)
if reporte["ok"]:
    inventory_df = reporte["updated_frames"]["inventory_df"]
    transaction_df = reporte["updated_frames"]["transaction_df"]
utils.print_html(inventory_df[["name", "quantity_in_stock"]], title="Inventario después (Sport: 11 → 1)")
utils.print_html(transaction_df, title="Caja después")

# %% [markdown]
# ## 7. Para llevarse
#
# - **El LLM propone, el código dispone.** El plan es un dato (JSON) que se puede leer,
#   guardar y revisar antes de ejecutar. El executor no tiene nada de LLM.
# - **Catálogo cerrado.** Si una tool no está en `TOOL_REGISTRY`, el plan falla con un
#   mensaje claro. Es la diferencia entre "el modelo puede hacer cualquier cosa" y "el
#   modelo puede hacer estas ocho cosas".
# - **Defensa en profundidad.** El planner pide validaciones, el reflector controla que
#   estén, y el executor tiene las suyas que no dependen de nadie.
# - **El estado cambia solo cuando vos lo decidís**, reasignando los DataFrames.
#
# ## Si te sobra tiempo
#
# Consignas abiertas (no están resueltas en este notebook; ver el workbook):
#
# 1. Agregá una tool `get_low_stock(threshold)` al registro y al catálogo, y pedile al
#    planner "¿qué modelos están por agotarse?".
# 2. Medí cuántas veces el reflector cambia el borrador en 5 pedidos distintos. ¿Vale lo
#    que cuesta (una llamada al modelo fuerte por pedido)?
# 3. Probá un pedido ambiguo ("quiero unos anteojos") y mirá qué hace el planner. ¿Cómo
#    cambiarías las reglas para que pida aclaraciones en vez de inventar?

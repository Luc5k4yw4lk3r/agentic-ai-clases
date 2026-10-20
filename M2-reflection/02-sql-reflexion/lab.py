# %% [markdown]
# # SQL con reflexión: de la pregunta en castellano a la consulta correcta
# **Módulo 2 · Lab 02.** Un flujo que convierte una pregunta en lenguaje natural en SQL,
# la ejecuta contra una base real y usa el **resultado de esa ejecución** como feedback
# para que el modelo corrija su propia consulta.
#
# ## Objetivos
# Al terminar vas a poder:
# - Pedirle a un LLM que genere SQL a partir de un schema y una pregunta.
# - Distinguir reflexión "en papel" (el modelo relee su SQL) de reflexión con
#   **feedback externo** (el modelo ve el resultado real de ejecutarla).
# - Pedir respuestas en JSON y parsearlas con validación explícita.
# - Encadenar todo en un workflow que muestra si la V2 cambió respecto de la V1.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. (Repaso) En el lab anterior, ¿qué recibía `revisar_borrador` para poder mejorar el ensayo?
#    a) Solo la consigna. b) El borrador y la crítica. c) El nombre del modelo.
# 2. (Repaso) ¿Dónde está el texto de la respuesta en el objeto que devuelve `client.chat.completions.create`?
#    a) `response.text`. b) `response.choices[0].message.content`. c) `response.content`.
# 3. Un LLM revisa una consulta SQL leyendo solo el texto de la consulta y dice "está bien". ¿Qué tipo de error **no** puede detectar así?
#    a) Un nombre de columna mal escrito. b) Un error de signo en los datos (por ejemplo, ventas guardadas como cantidades negativas). c) Un `SELECT` sin `FROM`.
# 4. ¿Qué le aporta al modelo ver el **resultado** de ejecutar la consulta, además del SQL?
#    a) Nada, el SQL ya lo dice todo. b) Evidencia concreta: si el total de ventas es negativo, algo está mal aunque la consulta "se vea bien". c) Solo sirve para ahorrar tokens.
# 5. SQL: en una tabla donde cada venta se guarda con `qty_delta = -3` (tres unidades que salieron), ¿cuánto da `SUM(qty_delta * unit_price)` para las ventas?
#    a) Un número positivo (el total vendido). b) Un número negativo. c) Cero.

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (sin crítica no hay reflexión), 2-b (la forma del SDK),
# 3-b (el signo es una convención de los datos, invisible en el texto de la consulta),
# 4-b (feedback externo = evidencia; es el punto central del lab),
# 5-b (cantidad negativa por precio positivo da negativo; de ahí sale el caso guía del lab).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

import aisuite as ai

client = ai.Client()
AI_CHEAP = f"openai:{MODEL_CHEAP}"
AI_STRONG = f"openai:{MODEL_STRONG}"

import pandas as pd
import utils
from utils import mostrar_html

print("Modelo barato:", AI_CHEAP, "| Modelo fuerte:", AI_STRONG)

# %% [markdown]
# ## 1. Teoría breve: reflexión con feedback externo
#
# **Para qué.** En el lab anterior el crítico solo leía texto. Eso alcanza para un ensayo,
# pero cuando el modelo genera algo **ejecutable** (SQL, código, una consulta a una API)
# tenemos una fuente de verdad mucho mejor que su opinión: **ejecutarlo y mirar qué
# sale**. Un total de ventas negativo es una evidencia que ninguna relectura del SQL
# te da.
#
# **Por qué así.** El modelo no conoce los datos; conoce el schema. Si una convención de
# la base (por ejemplo, "las ventas se guardan con cantidad negativa") no está en el
# schema, el modelo no puede adivinarla. El resultado de la ejecución es la forma de
# que esa información le llegue.
#
# **Ejemplo.** Es la diferencia entre un programador que relee su código y uno que
# además corre los tests. El primero atrapa errores de sintaxis y de lógica evidente; el
# segundo atrapa los que dependen de los datos.
#
# ```mermaid
# flowchart LR
#   Q[Pregunta] --> G[generar_sql → V1]
#   G --> E1[ejecutar_sql V1 → tabla]
#   E1 --> R[refinar_sql_con_feedback<br/>ve pregunta + SQL + tabla → V2]
#   R --> E2[ejecutar_sql V2 → respuesta final]
# ```
#
# Vamos a construir las dos variantes (sin y con feedback) para ver la diferencia con
# el mismo caso.

# %% [markdown]
# ## 2. La base de datos: una tabla de eventos
#
# `utils.crear_db_transacciones` genera `data/productos.db` con una sola tabla,
# `transactions`. Cada fila es un **evento** sobre un producto, no un estado:
#
# | action | qué representa | qty_delta | unit_price |
# |---|---|---|---|
# | `insert` | alta del producto con stock inicial | positivo | precio inicial |
# | `restock` | reposición | positivo | NULL |
# | `sale` | venta | **negativo** (sale mercadería) | precio al momento de la venta |
# | `price_update` | cambio de precio | 0 | nuevo precio |
#
# Este modelo se llama *event sourcing*: no hay columna "stock" ni "ventas totales";
# se calculan sumando eventos. El stock actual de un producto es `SUM(qty_delta)`.
# Las ventas en dinero son `SUM(-qty_delta * unit_price)` **solo sobre las filas con
# `action = 'sale'`**. Ese signo negativo es la trampa del lab: no está en el schema y
# el modelo no lo puede saber hasta que ve un resultado.
#
# La base se genera con semilla fija (`seed=42`): todos tienen los mismos datos.

# %%
DB_PATH = utils.crear_db_transacciones("data/productos.db", seed=42)
schema = utils.obtener_schema(DB_PATH)
mostrar_html(schema, titulo="Schema que va a ver el modelo")

mostrar_html(
    utils.ejecutar_sql("SELECT action, COUNT(*) AS eventos, SUM(qty_delta) AS suma_qty FROM transactions GROUP BY action", DB_PATH),
    titulo="Eventos por tipo (fijate el signo de suma_qty en 'sale')",
)
mostrar_html(
    utils.ejecutar_sql("SELECT * FROM transactions WHERE product_id = 1 ORDER BY id LIMIT 8", DB_PATH),
    titulo="Primeros 8 eventos del producto 1",
)

# %% [markdown]
# ## 3. Ejemplo resuelto: pedir JSON y parsearlo con validación
#
# En este lab las funciones de reflexión devuelven **dos cosas**: un feedback y una SQL
# refinada. La forma más cómoda de pedir dos cosas a un LLM es un JSON. Dos reglas:
#
# 1. En el prompt, pedí **solo** el JSON, con los nombres de campo exactos.
# 2. Después de recibirlo, **parsealo y validá** que tenga lo que esperás. Nunca
#    `try/except` que devuelva algo "por defecto" en silencio.
#
# `utils.extraer_json` hace el parseo (tolera fences ```json y texto alrededor) y
# levanta `ValueError` si no hay JSON. Este helper está completo; mirá cómo se usa:

# %%
def pedir_json(instruccion: str, model: str = AI_STRONG) -> dict:
    """Manda la instrucción al modelo y devuelve la respuesta ya parseada como dict.

    Levanta ValueError (desde utils.extraer_json) si la respuesta no trae un JSON.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruccion}],
        temperature=0,
    )
    contenido = response.choices[0].message.content
    return utils.extraer_json(contenido)


# %%
# Prueba rápida del ejemplo resuelto (una llamada corta)
ejemplo = pedir_json(
    'Respondé solo con un JSON con dos campos: "capital" (string) y "poblacion_millones" (número) para Argentina.'
)
print(type(ejemplo), ejemplo)
assert "capital" in ejemplo, "El JSON no tiene el campo 'capital'"

# %% [markdown]
# ## 4. Paso 1: generar la consulta (V1)
#
# `generar_sql` recibe la pregunta y el schema y devuelve una consulta SQLite. Pedile
# al modelo **solo el SQL**, sin explicaciones. Aun así, a veces lo envuelve en
# ```sql ... ```; `utils.limpiar_sql` lo saca.
#
# Usá `temperature=0`: queremos la consulta más "probable", no creatividad.

# %%
def generar_sql(pregunta: str, schema: str, model: str = AI_STRONG) -> str:
    """Convierte una pregunta en lenguaje natural en una consulta SQL para SQLite.

    Args:
        pregunta: lo que quiere saber el usuario, en castellano.
        schema: el schema de la tabla, tal como lo devuelve utils.obtener_schema.
        model: modelo en formato aisuite.

    Returns:
        La consulta SQL, sin fences ni explicaciones.
    """
    # Paso 1: armar la instrucción (rol, schema, pregunta, "respondé solo con el SQL")
    ### BEGIN SOLUTION
    ### STUDENT: instruccion = f"""..."""  # Completá: sos un asistente SQL para SQLite; incluí {schema} y {pregunta}
    instruccion = f"""Sos un asistente experto en SQL para SQLite.
Dado el schema y la pregunta del usuario, escribí UNA consulta SQL que la responda.

Schema:
{schema}

Pregunta del usuario:
{pregunta}

Respondé únicamente con el SQL, sin explicaciones ni formato markdown.
"""
    ### END SOLUTION
    # Paso 2: llamar al modelo con temperature=0 y devolver el SQL limpio (utils.limpiar_sql)
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruccion}],
        temperature=0,
    )
    return utils.limpiar_sql(response.choices[0].message.content)
    ### END SOLUTION


# %%
# Prueba rápida con el caso guía del lab
pregunta = "¿Qué color de producto tiene las mayores ventas totales en dinero?"

sql_v1 = generar_sql(pregunta, schema)
mostrar_html(pregunta, titulo="Pregunta")
mostrar_html(sql_v1, titulo="SQL V1")

df_v1 = utils.ejecutar_sql(sql_v1, DB_PATH)
mostrar_html(df_v1, titulo="Resultado de V1")

# %% [markdown]
# Mirá el resultado. Si el modelo multiplicó `qty_delta * unit_price` sin invertir el
# signo, el total te va a dar **negativo**. La consulta es sintácticamente válida y
# "parece" correcta, pero la respuesta no tiene sentido: nadie vende -190.000 pesos.
#
# Si en tu corrida el modelo ya puso `ABS()` o `-qty_delta`, no pasa nada: el flujo
# sigue igual y vas a ver que la reflexión confirma en vez de corregir. Más abajo
# comparamos de verdad si V2 cambió respecto de V1.
#
# > **Nota:** los nombres de columnas (`color`, `qty_delta`) están en inglés porque
# > así viene la base del material original. La pregunta y los prompts van en español.

# %% [markdown]
# ## 5. Paso 2a: reflexionar "en papel" (sin ejecutar)
#
# Primera variante: el modelo relee su consulta contra la pregunta y el schema, y dice
# si la mejora. **No ve datos.** Devuelve una tupla `(feedback, sql_refinado)`.
#
# Pedile un JSON con exactamente estos dos campos:
#
# ```json
# {"feedback": "<1 a 3 oraciones>", "sql_refinado": "<SQL final>"}
# ```
#
# Si la consulta ya está bien, el modelo tiene que devolverla sin cambios en
# `sql_refinado`. Después del parseo, validá que los dos campos existan y que
# `sql_refinado` no esté vacío: si falta algo, `ValueError` con mensaje claro.

# %%
def refinar_sql(pregunta: str, sql: str, schema: str, model: str = AI_STRONG) -> tuple[str, str]:
    """Revisa la consulta leyendo solo su texto (sin ejecutarla) y propone una versión refinada.

    Returns:
        (feedback, sql_refinado). Si el modelo considera que está bien, sql_refinado == sql.

    Raises:
        ValueError: si la respuesta no es un JSON con los campos esperados.
    """
    # Paso 1: instrucción que pide evaluar y devolver JSON con "feedback" y "sql_refinado"
    ### BEGIN SOLUTION
    ### STUDENT: instruccion = f"""..."""  # Completá: incluí {pregunta}, {sql}, {schema} y el formato JSON exacto
    instruccion = f"""Sos un revisor de SQL para SQLite.

Pregunta del usuario:
{pregunta}

Consulta propuesta:
{sql}

Schema:
{schema}

Paso 1: evaluá brevemente si la consulta responde del todo a la pregunta.
Paso 2: si hace falta mejorarla, escribí la consulta corregida. Si ya está bien, devolvela sin cambios.

Respondé únicamente con un JSON con exactamente estos dos campos:
{{"feedback": "<1 a 3 oraciones>", "sql_refinado": "<SQL final para ejecutar>"}}
"""
    ### END SOLUTION
    # Paso 2: llamar al modelo (podés reusar pedir_json) y validar los campos
    ### BEGIN SOLUTION
    obj = pedir_json(instruccion, model=model)
    if "feedback" not in obj or "sql_refinado" not in obj:
        raise ValueError(f"El JSON del modelo no tiene los campos 'feedback' y 'sql_refinado'. Vino: {sorted(obj.keys())}")
    feedback = str(obj["feedback"]).strip()
    sql_refinado = utils.limpiar_sql(str(obj["sql_refinado"]))
    if not sql_refinado:
        raise ValueError("El modelo devolvió 'sql_refinado' vacío.")
    return feedback, sql_refinado
    ### END SOLUTION


# %%
# Prueba rápida: ¿la relectura detecta el problema del signo?
feedback_papel, sql_v2_papel = refinar_sql(pregunta, sql_v1, schema)

mostrar_html(feedback_papel, titulo="Feedback (reflexión en papel)")
mostrar_html(sql_v2_papel, titulo="SQL V2 (reflexión en papel)")

cambio_papel = not utils.misma_sql(sql_v1, sql_v2_papel)
print("¿La V2 cambió respecto de la V1?", cambio_papel)
df_v2_papel = utils.ejecutar_sql(sql_v2_papel, DB_PATH)
mostrar_html(df_v2_papel, titulo="Resultado de V2 (en papel)", estilo="ok" if cambio_papel else "alerta")

# %% [markdown]
# Lo típico es que el feedback diga algo como "la consulta es correcta" y devuelva la
# misma SQL. Tiene sentido: leyendo solo el texto, nada indica que `qty_delta` sea
# negativo en las ventas. Es una convención de los datos, no del SQL. En algunas
# corridas el modelo lo sospecha por el nombre `qty_delta` y lo corrige; por eso
# comparamos de verdad en vez de asumir.
#
# **Anotá qué pasó en tu corrida.** Lo vamos a contrastar con la variante siguiente.

# %% [markdown]
# ## 6. Paso 2b: reflexionar con feedback externo (viendo el resultado)
#
# Segunda variante: igual que la anterior, pero el prompt incluye **la tabla que
# devolvió la ejecución de V1**. Para pasarle un DataFrame a un modelo lo convertimos a
# texto con `df.to_markdown(index=False)` (necesita el paquete `tabulate`, ya instalado).
#
# Ahora el modelo tiene evidencia: un total negativo. Esperamos que lo note y corrija
# el signo (`-qty_delta` o `ABS(qty_delta)`).
#
# Si `df_resultado` tiene una columna `error` (porque la V1 ni siquiera corrió), eso
# también es feedback: el modelo ve el mensaje de SQLite y puede arreglar la sintaxis.

# %%
def refinar_sql_con_feedback(
    pregunta: str,
    sql: str,
    df_resultado: pd.DataFrame,
    schema: str,
    model: str = AI_STRONG,
) -> tuple[str, str]:
    """Revisa la consulta viendo el resultado real de ejecutarla y propone una versión refinada.

    Args:
        df_resultado: lo que devolvió utils.ejecutar_sql(sql). Puede ser una tabla de error.

    Returns:
        (feedback, sql_refinado).

    Raises:
        ValueError: si la respuesta no es un JSON con los campos esperados.
    """
    # Paso 1: convertir el resultado a texto para el prompt
    ### BEGIN SOLUTION
    ### STUDENT: resultado_texto = None  # Pista: df_resultado.to_markdown(index=False)
    resultado_texto = df_resultado.to_markdown(index=False)
    ### END SOLUTION
    # Paso 2: instrucción igual a la de refinar_sql, pero agregando el resultado de la ejecución
    ### BEGIN SOLUTION
    ### STUDENT: instruccion = f"""..."""  # Completá: {pregunta}, {sql}, {resultado_texto}, {schema}, formato JSON
    instruccion = f"""Sos un revisor de SQL para SQLite.

Pregunta del usuario:
{pregunta}

Consulta propuesta:
{sql}

Resultado de ejecutar esa consulta:
{resultado_texto}

Schema:
{schema}

Paso 1: evaluá si el RESULTADO responde de verdad a la pregunta. Prestá atención a signos,
magnitudes, filtros que falten y agrupaciones. Si hay una columna "error", la consulta falló.
Paso 2: si hace falta, escribí la consulta corregida. Si ya está bien, devolvela sin cambios.

Respondé únicamente con un JSON con exactamente estos dos campos:
{{"feedback": "<1 a 3 oraciones con la evaluación y qué cambiaste>", "sql_refinado": "<SQL final para ejecutar>"}}
"""
    ### END SOLUTION
    # Paso 3: llamar, parsear y validar (igual que en refinar_sql)
    ### BEGIN SOLUTION
    obj = pedir_json(instruccion, model=model)
    if "feedback" not in obj or "sql_refinado" not in obj:
        raise ValueError(f"El JSON del modelo no tiene los campos 'feedback' y 'sql_refinado'. Vino: {sorted(obj.keys())}")
    feedback = str(obj["feedback"]).strip()
    sql_refinado = utils.limpiar_sql(str(obj["sql_refinado"]))
    if not sql_refinado:
        raise ValueError("El modelo devolvió 'sql_refinado' vacío.")
    return feedback, sql_refinado
    ### END SOLUTION


# %%
# Prueba rápida: misma V1, pero ahora el modelo ve el resultado
feedback_ext, sql_v2_ext = refinar_sql_con_feedback(pregunta, sql_v1, df_v1, schema)

mostrar_html(feedback_ext, titulo="Feedback (con resultado de la ejecución)")
mostrar_html(sql_v2_ext, titulo="SQL V2 (con feedback externo)")

cambio_ext = not utils.misma_sql(sql_v1, sql_v2_ext)
print("¿La V2 cambió respecto de la V1?", cambio_ext)
df_v2_ext = utils.ejecutar_sql(sql_v2_ext, DB_PATH)
mostrar_html(df_v2_ext, titulo="Resultado de V2 (con feedback externo)", estilo="ok" if cambio_ext else "alerta")

# %% [markdown]
# ### Comparación
#
# | | En papel | Con feedback externo |
# |---|---|---|
# | ¿Qué ve el modelo? | pregunta + SQL + schema | lo mismo **+ la tabla resultado** |
# | ¿Cambió la SQL? | (mirá `cambio_papel`) | (mirá `cambio_ext`) |
# | ¿El total es positivo? | (mirá `df_v2_papel`) | (mirá `df_v2_ext`) |
#
# Si en tu corrida las dos variantes corrigieron el signo, probá la pregunta
# "¿Cuál es el stock actual de cada categoría?" y fijate si alguna variante filtra por
# `action = 'sale'` cuando no debería.

# %%
print(f"En papel:      cambió={cambio_papel!s:5}  total={df_v2_papel.iloc[0, -1] if 'error' not in df_v2_papel else 'ERROR'}")
print(f"Con feedback:  cambió={cambio_ext!s:5}  total={df_v2_ext.iloc[0, -1] if 'error' not in df_v2_ext else 'ERROR'}")

# %% [markdown]
# ## 7. Combinar: el workflow completo
#
# `correr_workflow_sql` encadena todo: schema → V1 → ejecutar → reflexionar con
# feedback → V2 → ejecutar. Devuelve un diccionario con todas las piezas para que
# puedas inspeccionarlas, y muestra en pantalla **si la V2 cambió de verdad** (no un
# título fijo que diga "mejorado").
#
# Fijate que usa dos parámetros de modelo: uno para generar y otro para reflexionar.
# Así podés probar barato/fuerte en cada rol.

# %%
def correr_workflow_sql(
    db_path: str,
    pregunta: str,
    model_generacion: str = AI_CHEAP,
    model_reflexion: str = AI_STRONG,
    mostrar: bool = True,
) -> dict:
    """Workflow completo: pregunta → SQL V1 → ejecutar → reflexión con feedback → SQL V2 → ejecutar.

    Returns:
        dict con: schema, sql_v1, df_v1, feedback, sql_v2, df_v2, cambio (bool).
    """
    # Paso 1: schema y SQL V1
    ### BEGIN SOLUTION
    schema = utils.obtener_schema(db_path)
    sql_v1 = generar_sql(pregunta, schema, model=model_generacion)
    ### END SOLUTION

    # Paso 2: ejecutar V1 y reflexionar con el resultado como feedback → V2
    ### BEGIN SOLUTION
    df_v1 = utils.ejecutar_sql(sql_v1, db_path)
    feedback, sql_v2 = refinar_sql_con_feedback(pregunta, sql_v1, df_v1, schema, model=model_reflexion)
    ### END SOLUTION

    # Paso 3: ejecutar V2 y comparar de verdad si cambió respecto de V1
    ### BEGIN SOLUTION
    df_v2 = utils.ejecutar_sql(sql_v2, db_path)
    cambio = not utils.misma_sql(sql_v1, sql_v2)
    ### END SOLUTION

    resultado = {
        "schema": schema, "sql_v1": sql_v1, "df_v1": df_v1,
        "feedback": feedback, "sql_v2": sql_v2, "df_v2": df_v2, "cambio": cambio,
    }
    if mostrar:
        mostrar_html(pregunta, titulo="Pregunta")
        mostrar_html(sql_v1, titulo="Paso 1 — SQL V1")
        mostrar_html(df_v1, titulo="Paso 2 — Resultado de V1")
        mostrar_html(feedback, titulo="Paso 3 — Feedback de la reflexión")
        if cambio:
            mostrar_html(sql_v2, titulo="Paso 4 — SQL V2 (la reflexión CAMBIÓ la consulta)", estilo="ok")
        else:
            mostrar_html(sql_v2, titulo="Paso 4 — SQL V2 (la reflexión NO cambió la consulta)", estilo="alerta")
        mostrar_html(df_v2, titulo="Paso 5 — Resultado de V2 (respuesta final)")
    return resultado


# %%
# Prueba rápida con el caso guía y modelo barato para generar
r = correr_workflow_sql(DB_PATH, "¿Qué color de producto tiene las mayores ventas totales en dinero?")
print("¿Cambió?", r["cambio"])

# %% [markdown]
# ## 8. Probá otras preguntas
#
# Cada una esconde una trampa distinta del modelo de eventos. Antes de correrlas,
# anotá qué esperás que haga mal la V1.
#
# - "¿Cuál es el stock actual de cada categoría?" (hay que sumar **todos** los
#   `qty_delta`, no solo las ventas)
# - "¿Cuál es el precio actual de cada producto?" (es el `unit_price` del **último**
#   evento con precio, no el promedio)
# - "¿Qué marca vendió más unidades?" (unidades, no dinero; signo otra vez)
# - "¿Cuántos productos hay en el catálogo?" (contar `product_id` distintos, no filas)

# %%
preguntas_extra = [
    "¿Cuál es el stock actual de cada categoría?",
    "¿Qué marca vendió más unidades?",
]
for p in preguntas_extra:
    r = correr_workflow_sql(DB_PATH, p, mostrar=False)
    print(f"\n{p}\n  V1: {r['sql_v1'][:90]}...\n  cambió: {r['cambio']}\n  feedback: {r['feedback'][:140]}")

# %% [markdown]
# ## 9. Si te sobra tiempo
#
# Consignas abiertas (sin solución en el notebook; ideas en el workbook):
#
# 1. **Documentar la convención.** Agregá al `schema` una línea que diga "qty_delta es
#    negativo en las ventas". ¿La V1 ya sale bien? ¿Entonces para qué sirve la reflexión?
# 2. **Dos rondas.** Si `cambio` es True, volvé a ejecutar y a reflexionar sobre la V2.
#    ¿Converge o sigue cambiando cosas?
# 3. **Modelo barato para reflexionar.** Corré el workflow con `model_reflexion=AI_CHEAP`.
#    ¿Detecta el signo igual?
# 4. **Romper la V1 a propósito.** Pasale a `refinar_sql_con_feedback` una SQL con una
#    columna inexistente y mirá cómo usa la tabla `error` para arreglarla.

# %% [markdown]
# ## Para cerrar
#
# - Reflexionar "en papel" atrapa errores de forma; reflexionar **con el resultado**
#   atrapa errores de fondo que dependen de los datos.
# - Cuando el modelo devuelve JSON, parseá y validá. Un fallback silencioso que
#   devuelve la V1 como si fuera la V2 es peor que un error.
# - Mostrar "mejorado" en un título no hace que esté mejorado: comparalo.
# - En el próximo lab el feedback externo va a ser una **imagen**: el modelo va a mirar
#   el gráfico que generó su propio código.

# %% [markdown]
# # Gráficos con reflexión multimodal: el modelo mira lo que dibujó
# **Módulo 2 · Lab 03.** Un LLM escribe código matplotlib (V1), lo ejecutamos, y un
# modelo con visión **mira el PNG resultante** junto con el código, lo critica y devuelve
# una V2 mejorada.
#
# ## Objetivos
# Al terminar vas a poder:
# - Pedirle a un LLM código Python delimitado por etiquetas y extraerlo con una regex
#   que falla con un error claro cuando no hay etiquetas.
# - Ejecutar código generado con `exec` en un namespace controlado, capturando el error
#   como texto en vez de romper el notebook.
# - Armar un mensaje **multimodal** (texto + imagen en base64) con el SDK de `openai`.
# - Encadenar todo en un workflow y discutir qué puede y qué no puede ver la reflexión.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. (Repaso) En el lab de SQL, ¿qué le dimos al modelo para que detectara el error de signo que no veía leyendo la consulta?
#    a) Un prompt más largo. b) El resultado real de ejecutar la consulta. c) Un modelo más grande.
# 2. (Repaso) Si el modelo devuelve un JSON mal formado, ¿qué tiene que hacer nuestro código?
#    a) Devolver un valor por defecto en silencio. b) Levantar un error con un mensaje claro. c) Reintentar infinitamente.
# 3. ¿Qué información tiene un modelo con visión que mira el PNG del gráfico y que **no** tiene leyendo solo el código matplotlib?
#    a) Ninguna, el código determina la imagen. b) Cómo quedó realmente: etiquetas superpuestas, colores indistinguibles, barras vacías, leyenda tapando datos. c) El tamaño del archivo.
# 4. ¿Por qué el código generado va entre etiquetas `<execute_python>` ... `</execute_python>` en vez de pedirlo "suelto"?
#    a) Porque Python lo requiere. b) Para poder separar con una regex el código de cualquier explicación que agregue el modelo, y detectar cuando no mandó código. c) Para que corra más rápido.
# 5. Python: `exec(codigo, {"df": df})`. ¿Qué hace el segundo argumento?
#    a) Es el namespace global donde corre el código: el código ve `df` y nada más de tu notebook. b) Es una lista de módulos a importar. c) Es el archivo de salida.

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (feedback externo), 2-b (validación explícita, nunca fallback silencioso),
# 3-b (el render depende de los datos y del layout; el código no lo revela),
# 4-b (delimitar para extraer y para fallar fuerte si no hay código),
# 5-a (namespace controlado; además `exec` escribe ahí las variables que el código cree).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

# En este lab usamos el SDK de OpenAI directo (sin aisuite): el mensaje con imagen se arma a mano.
from openai import OpenAI

client = OpenAI()

import re
import traceback

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # backend sin ventana: los gráficos se guardan a archivo, no se muestran
import matplotlib.pyplot as plt

import utils
from utils import mostrar_html

borrados = utils.borrar_pngs("data")      # limpiamos gráficos de corridas anteriores
print("PNG borrados de corridas previas:", borrados or "ninguno")
print("Modelo barato:", MODEL_CHEAP, "| Modelo fuerte (ve imágenes):", MODEL_STRONG)

# %% [markdown]
# ## 1. Teoría breve: reflexión multimodal
#
# **Para qué.** En el lab 02 el feedback externo era una tabla. Acá el artefacto que
# genera el modelo es **código que produce una imagen**. Leer el código no alcanza para
# saber si el gráfico quedó bien: etiquetas que se pisan, colores iguales, una barra
# vacía porque un filtro no matcheó. Eso solo se ve **mirando** el gráfico. Los modelos
# con visión (como `gpt-4.1`) aceptan imágenes en el mensaje, así que podemos darle el
# PNG y pedirle crítica + código corregido.
#
# **Por qué así.** El flujo tiene cuatro piezas que conviene separar porque cada una
# puede fallar de forma distinta:
#
# ```mermaid
# flowchart LR
#   I[Instrucción] --> G[generar_codigo_grafico → texto con etiquetas]
#   G --> X1[extraer_codigo → código Python]
#   X1 --> E1[ejecutar_codigo → chart_v1.png o traceback]
#   E1 --> R[reflexionar_sobre_grafico<br/>ve PNG + código → JSON + código V2]
#   R --> X2[extraer_codigo] --> E2[ejecutar_codigo → chart_v2.png]
# ```
#
# - El modelo puede no mandar las etiquetas → `extraer_codigo` tiene que fallar fuerte.
# - El código puede romperse → `ejecutar_codigo` devuelve el traceback como texto (es
#   feedback útil, no un motivo para cortar).
# - El modelo puede no mandar el JSON → `extraer_json` levanta `ValueError`.
#
# **Ejemplo.** Un diseñador que recibe la instrucción "comparar ventas Q1 2024 vs 2025",
# hace un boceto, lo imprime, lo mira con el cliente, y recién ahí lo corrige.

# %% [markdown]
# ## 2. Los datos: ventas de una máquina de café
#
# `data/coffee_sales.csv` tiene una fila por venta. Antes de pedirle nada al modelo,
# miramos qué columnas hay **de verdad** (la descripción del prompt se genera desde el
# DataFrame, no a mano).

# %%
df = utils.cargar_datos("data/coffee_sales.csv")
print(df.shape)
mostrar_html(df.sample(n=5, random_state=0), titulo="Cinco ventas al azar")

descripcion_columnas = utils.describir_columnas(df)
mostrar_html(descripcion_columnas, titulo="Columnas que va a ver el modelo")

# %% [markdown]
# ### Punto de discusión: ¿cuántos datos hay en cada trimestre?
#
# La instrucción guía del lab es *"comparar las ventas de café del Q1 de 2024 y el Q1
# de 2025"*. Antes de graficar, contá las ventas por año y trimestre. Fijate qué meses
# tiene el Q1 de 2024.

# %%
conteo = df.groupby(["year", "quarter"]).agg(ventas=("price", "size"), ingresos=("price", "sum")).reset_index()
mostrar_html(conteo, titulo="Ventas e ingresos por año y trimestre")

meses_q1 = df[df["quarter"] == 1].groupby(["year", "month"]).size().reset_index(name="ventas")
mostrar_html(meses_q1, titulo="Meses presentes en cada Q1", estilo="alerta")

# %% [markdown]
# El Q1 de 2024 **solo tiene marzo** (el dataset arranca el 1 de marzo de 2024); el Q1
# de 2025 tiene enero, febrero y marzo. Cualquier gráfico que compare "Q1 vs Q1" sin
# aclararlo va a mostrar que 2025 "creció" más de 4 veces, y es un artefacto de los
# datos. Guardá esta pregunta para después: **¿la reflexión lo detecta mirando el
# gráfico?** Es una buena prueba de los límites del patrón.

# %% [markdown]
# ## 3. Ejemplo resuelto: pedir código entre etiquetas
#
# `generar_codigo_grafico` está completa. Pide al modelo código matplotlib delimitado
# por `<execute_python>` y `</execute_python>`, con requisitos claros: usar `df` que ya
# existe, guardar en una ruta dada, no llamar a `plt.show()`, cerrar la figura. La
# descripción de columnas se inyecta desde `describir_columnas(df)`.

# %%
def generar_codigo_grafico(instruccion: str, descripcion_columnas: str, ruta_salida: str, model: str = MODEL_CHEAP) -> str:
    """Pide al modelo código matplotlib que grafique `df` según la instrucción.

    Devuelve el texto completo de la respuesta (con las etiquetas <execute_python>).
    """
    prompt = f"""Sos un experto en visualización de datos.

Respondé ESTRICTAMENTE con este formato, sin explicaciones fuera de las etiquetas:

<execute_python>
# código Python válido
</execute_python>

El código tiene que crear un gráfico a partir de un DataFrame de pandas llamado `df`
que YA está cargado, con estas columnas:
{descripcion_columnas}

Instrucción del usuario: {instruccion}

Requisitos del código:
1. No leer archivos: usá `df` directamente.
2. Usá matplotlib (podés usar pandas para agrupar). Nada de seaborn.
3. Título claro, ejes etiquetados y leyenda si hace falta. Textos en español.
4. Guardá la figura en '{ruta_salida}' con dpi=150 usando plt.savefig.
5. No llames a plt.show(). Terminá con plt.close().
6. Incluí todos los import que uses (matplotlib.pyplot, pandas).
"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content


# %%
INSTRUCCION = "Hacé un gráfico que compare las ventas de café del primer trimestre (Q1) de 2024 con las del Q1 de 2025."
RUTA_V1 = "data/chart_v1.png"
RUTA_V2 = "data/chart_v2.png"

respuesta_v1 = generar_codigo_grafico(INSTRUCCION, descripcion_columnas, RUTA_V1)
mostrar_html(respuesta_v1, titulo="Respuesta del modelo (V1, con etiquetas)")

# %% [markdown]
# ## 4. Paso 1: extraer el código
#
# `extraer_codigo` recibe el texto completo y devuelve **solo** lo que está entre las
# etiquetas. Usá `re.search` con el patrón `<execute_python>([\s\S]*?)</execute_python>`:
# `[\s\S]*?` es "cualquier caracter, incluidos saltos de línea, la menor cantidad posible".
#
# Si no hay etiquetas, levantá `ValueError` con un mensaje en español que incluya el
# principio de la respuesta. **Nunca** `if match:` que siga adelante como si nada: el
# lab original hacía eso y, cuando el modelo olvidaba las etiquetas, el notebook
# mostraba el PNG de la corrida anterior sin avisar.

# %%
def extraer_codigo(texto: str) -> str:
    """Devuelve el código Python que está entre <execute_python> y </execute_python>.

    Raises:
        ValueError: si el texto no tiene las etiquetas.
    """
    ### BEGIN SOLUTION
    ### STUDENT: match = None  # Pista: re.search(r"<execute_python>([\s\S]*?)</execute_python>", texto)
    ### STUDENT: raise NotImplementedError("Completá esta función")
    match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", texto)
    if match is None:
        recorte = texto.strip().replace("\n", " ")[:150]
        raise ValueError(
            "La respuesta del modelo no tiene las etiquetas <execute_python>...</execute_python>. "
            f"Empezaba así: {recorte!r}"
        )
    codigo = match.group(1).strip()
    if not codigo:
        raise ValueError("Las etiquetas <execute_python> están vacías: el modelo no mandó código.")
    return codigo
    ### END SOLUTION


# %%
# Prueba rápida (sin API): un caso con etiquetas y uno sin
print(extraer_codigo("bla bla <execute_python>\nprint('hola')\n</execute_python> chau"))
try:
    extraer_codigo("Acá va el código:\n```python\nprint('sin etiquetas')\n```")
    print("ERROR: tendría que haber levantado ValueError")
except ValueError as e:
    print("ValueError esperado ->", e)

codigo_v1 = extraer_codigo(respuesta_v1)
mostrar_html(codigo_v1, titulo="Código V1 extraído")

# %% [markdown]
# ## 5. Paso 2: ejecutar el código
#
# `ejecutar_codigo` corre el código con `exec` en un namespace que solo contiene `df`.
# Devuelve `None` si todo salió bien, o el **traceback como string** si falló. No
# levanta la excepción: queremos que el flujo siga y que el error pueda usarse como
# feedback para la reflexión.
#
# `traceback.format_exc()` devuelve el traceback de la excepción que se está manejando
# dentro de un `except`.
#
# > Ejecutar código generado por un modelo es exactamente eso: ejecutar código que no
# > escribiste. En un lab con un CSV local no hay riesgo real, pero en producción esto
# > se hace en un sandbox. Lo retomamos en M3.

# %%
def ejecutar_codigo(codigo: str, df: pd.DataFrame) -> str | None:
    """Ejecuta el código con `df` disponible. Devuelve None si anduvo, o el traceback como texto.

    Args:
        codigo: código Python (ya sin etiquetas).
        df: el DataFrame que el código espera encontrar como `df`.
    """
    ### BEGIN SOLUTION
    ### STUDENT: namespace = {"df": df}
    ### STUDENT: raise NotImplementedError("Completá: exec(codigo, namespace) dentro de try/except; en el except devolvé traceback.format_exc()")
    namespace = {"df": df}
    try:
        exec(codigo, namespace)
        return None
    except Exception:
        plt.close("all")  # si falló a mitad de camino, no dejar figuras abiertas
        return traceback.format_exc()
    ### END SOLUTION


# %%
# Prueba rápida (sin API): un snippet que funciona y uno que falla
ok = ejecutar_codigo("import matplotlib.pyplot as plt\nplt.figure(); plt.bar(['a','b'], [1,2]); plt.savefig('data/prueba.png'); plt.close()", df)
print("Snippet correcto ->", ok)
fallo = ejecutar_codigo("print(df['columna_inexistente'])", df)
print("Snippet roto ->", fallo.splitlines()[-1] if fallo else fallo)

# Y ahora el código V1 del modelo
error_v1 = ejecutar_codigo(codigo_v1, df)
if error_v1:
    mostrar_html(error_v1, titulo="El código V1 falló", estilo="alerta")
else:
    mostrar_html(RUTA_V1, titulo="Gráfico V1", es_imagen=True)

# %% [markdown]
# ## 6. Paso 3: reflexionar mirando el gráfico
#
# Acá está la novedad del lab. `reflexionar_sobre_grafico` arma un mensaje con **dos
# partes** en `content`: un bloque de texto (la consigna de crítica, con el código V1
# para contexto) y un bloque de imagen con el PNG en base64:
#
# ```python
# messages=[{
#     "role": "user",
#     "content": [
#         {"type": "text", "text": prompt},
#         {"type": "image_url", "image_url": {"url": "data:image/png;base64,...."}},
#     ],
# }]
# ```
#
# `utils.imagen_a_data_url(ruta)` te da el string `data:image/png;base64,...`.
#
# Al modelo le pedimos una respuesta en dos partes: primero una línea con un JSON
# `{"feedback": "..."}` y después el código V2 entre etiquetas. Parseamos cada parte con
# su helper: `utils.extraer_json` para el feedback (busca solo antes de la etiqueta) y
# tu `extraer_codigo` para el código. Devolvemos `(feedback_dict, codigo_v2)`.

# %%
def reflexionar_sobre_grafico(
    ruta_png: str,
    instruccion: str,
    codigo_v1: str,
    ruta_salida_v2: str,
    descripcion_columnas: str,
    model: str = MODEL_STRONG,
) -> tuple[dict, str]:
    """Critica el gráfico (imagen) y su código, y devuelve (feedback, codigo_v2).

    Args:
        ruta_png: el PNG de la V1 que el modelo va a mirar.
        instruccion: la instrucción original del usuario.
        codigo_v1: el código que generó el PNG (contexto).
        ruta_salida_v2: dónde tiene que guardar el gráfico el código V2.
        descripcion_columnas: columnas de `df`, desde utils.describir_columnas.
        model: tiene que ser un modelo con visión (MODEL_STRONG).

    Returns:
        (feedback, codigo_v2): feedback es un dict con al menos la clave "feedback";
        codigo_v2 es código Python ya sin etiquetas.

    Raises:
        ValueError: si falta el JSON o las etiquetas en la respuesta.
    """
    prompt = f"""Sos un experto en visualización de datos. Mirá el gráfico adjunto y leé el código
que lo generó. Tu tarea: criticar el gráfico respecto de la instrucción del usuario y
devolver código matplotlib mejorado.

Instrucción del usuario: {instruccion}

Código original (contexto):
{codigo_v1}

Columnas disponibles en `df`:
{descripcion_columnas}

FORMATO DE RESPUESTA (estricto):
1) Primera línea: un JSON con una sola clave "feedback" (2 a 4 oraciones: qué está mal
   o qué falta en el gráfico, mirando la imagen; si los datos muestran algo raro, decilo).
   Ejemplo: {{"feedback": "Las etiquetas del eje x se superponen y falta la leyenda."}}
2) Después, SOLO el código mejorado entre <execute_python> y </execute_python>.

Restricciones del código: usar `df` ya cargado (no leer archivos), matplotlib y pandas
solamente, incluir todos los import, textos en español, guardar en '{ruta_salida_v2}'
con dpi=150, no llamar a plt.show(), terminar con plt.close(). Nada de markdown ni
backticks fuera de las dos partes.
"""
    # Paso 1: codificar la imagen como data URL
    ### BEGIN SOLUTION
    ### STUDENT: data_url = None  # Pista: utils.imagen_a_data_url(ruta_png)
    data_url = utils.imagen_a_data_url(ruta_png)
    ### END SOLUTION

    # Paso 2: llamar al modelo con un mensaje multimodal (texto + imagen)
    ### BEGIN SOLUTION
    ### STUDENT: contenido = None  # Pista: content es una LISTA con un dict "text" y un dict "image_url"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0,
    )
    contenido = response.choices[0].message.content
    ### END SOLUTION

    # Paso 3: parsear las dos partes (JSON de feedback y código V2) y validar
    ### BEGIN SOLUTION
    feedback = utils.extraer_json(contenido)
    if "feedback" not in feedback:
        raise ValueError(f"El JSON del modelo no tiene la clave 'feedback'. Vino: {sorted(feedback.keys())}")
    codigo_v2 = extraer_codigo(contenido)
    return feedback, codigo_v2
    ### END SOLUTION


# %%
# Prueba rápida: el modelo fuerte mira el gráfico V1
feedback, codigo_v2 = reflexionar_sobre_grafico(RUTA_V1, INSTRUCCION, codigo_v1, RUTA_V2, descripcion_columnas)

mostrar_html(feedback["feedback"], titulo="Crítica del gráfico V1 (mirando la imagen)")
mostrar_html(codigo_v2, titulo="Código V2")

error_v2 = ejecutar_codigo(codigo_v2, df)
if error_v2:
    mostrar_html(error_v2, titulo="El código V2 falló", estilo="alerta")
elif not os.path.exists(RUTA_V2):
    mostrar_html(f"El código V2 corrió sin errores pero no creó {RUTA_V2}. Revisá la línea savefig: "
                 "probablemente guardó en la ruta de la V1.", titulo="V2 sin gráfico", estilo="alerta")
else:
    mostrar_html(RUTA_V2, titulo="Gráfico V2", es_imagen=True, estilo="ok")

# %% [markdown]
# ### ¿La reflexión notó lo del Q1 de 2024?
#
# Releé el feedback. ¿Dice algo sobre que 2024 tiene un solo mes de datos? Lo
# esperable es que critique **forma** (colores, etiquetas, tipo de gráfico) y no
# **datos**, porque el modelo ve el gráfico y el código, pero no vio la tabla de conteos
# por mes. Si querés que lo detecte, tenés que dárselo: eso es la extensión 1 de la
# sección "Si te sobra tiempo".

# %% [markdown]
# ## 7. Combinar: el workflow completo
#
# `correr_workflow` encadena las cuatro piezas con una lógica de control sencilla:
# si el código V1 falla, no hay PNG para mirar, así que le pasamos el traceback al
# modelo como "gráfico" no disponible y le pedimos que corrija. Eso lo dejamos simple:
# si V1 falla, el workflow corta con un mensaje claro y devuelve lo que tiene.

# %%
def correr_workflow(
    df: pd.DataFrame,
    instruccion: str,
    nombre_base: str = "data/chart",
    model_generacion: str = MODEL_CHEAP,
    model_reflexion: str = MODEL_STRONG,
    mostrar: bool = True,
) -> dict:
    """Instrucción → código V1 → PNG V1 → reflexión multimodal → código V2 → PNG V2.

    Returns:
        dict con: codigo_v1, ruta_v1, error_v1, feedback, codigo_v2, ruta_v2, error_v2.
        Si V1 falla, feedback/codigo_v2/ruta_v2/error_v2 quedan en None.
    """
    ruta_v1 = f"{nombre_base}_v1.png"
    ruta_v2 = f"{nombre_base}_v2.png"
    columnas = utils.describir_columnas(df)
    resultado = {"codigo_v1": None, "ruta_v1": ruta_v1, "error_v1": None,
                 "feedback": None, "codigo_v2": None, "ruta_v2": None, "error_v2": None}

    # Paso 1: generar y extraer el código V1, ejecutarlo
    ### BEGIN SOLUTION
    respuesta_v1 = generar_codigo_grafico(instruccion, columnas, ruta_v1, model=model_generacion)
    codigo_v1 = extraer_codigo(respuesta_v1)
    error_v1 = ejecutar_codigo(codigo_v1, df)
    resultado["codigo_v1"] = codigo_v1
    resultado["error_v1"] = error_v1
    ### END SOLUTION
    if mostrar:
        mostrar_html(codigo_v1, titulo="Paso 1 — Código V1")
        if error_v1:
            mostrar_html(error_v1, titulo="Paso 2 — V1 falló; no hay gráfico para reflexionar", estilo="alerta")
        else:
            mostrar_html(ruta_v1, titulo="Paso 2 — Gráfico V1", es_imagen=True)
    if error_v1:
        return resultado

    # Paso 2: reflexionar sobre el PNG V1 y ejecutar el código V2
    ### BEGIN SOLUTION
    feedback, codigo_v2 = reflexionar_sobre_grafico(ruta_v1, instruccion, codigo_v1, ruta_v2, columnas, model=model_reflexion)
    error_v2 = ejecutar_codigo(codigo_v2, df)
    resultado["feedback"] = feedback
    resultado["codigo_v2"] = codigo_v2
    resultado["ruta_v2"] = ruta_v2
    resultado["error_v2"] = error_v2
    ### END SOLUTION
    if mostrar:
        mostrar_html(feedback["feedback"], titulo="Paso 3 — Crítica mirando el gráfico")
        mostrar_html(codigo_v2, titulo="Paso 4 — Código V2")
        if error_v2:
            mostrar_html(error_v2, titulo="Paso 5 — V2 falló", estilo="alerta")
        elif not os.path.exists(ruta_v2):
            mostrar_html(f"El código V2 corrió pero no creó {ruta_v2} (revisá su línea savefig).",
                         titulo="Paso 5 — V2 sin gráfico", estilo="alerta")
        else:
            mostrar_html(ruta_v2, titulo="Paso 5 — Gráfico V2", es_imagen=True, estilo="ok")
    return resultado


# %%
# Prueba rápida con otra instrucción (y otro nombre de archivo para no pisar los anteriores)
r = correr_workflow(
    df,
    "Mostrá qué bebidas se venden más en cada franja horaria del día (mañana, tarde, noche).",
    nombre_base="data/bebidas_horario",
)
print("V1 falló:", bool(r["error_v1"]), "| V2 falló:", bool(r["error_v2"]))

# %% [markdown]
# ## 8. Si te sobra tiempo
#
# Consignas abiertas (sin solución en el notebook; ideas en el workbook):
#
# 1. **Darle los datos al crítico.** Agregá al prompt de `reflexionar_sobre_grafico` la
#    tabla `conteo` (ventas por año y trimestre) como texto. ¿Ahora detecta que el Q1
#    de 2024 está incompleto? ¿Qué hace el código V2 con eso: lo aclara en el título,
#    compara solo marzo, o lo ignora?
# 2. **Reflexión sobre el error.** Si `ejecutar_codigo` devuelve un traceback, en vez de
#    cortar el workflow mandáselo al modelo (sin imagen) y pedile una corrección.
#    Necesitás una variante de `reflexionar_sobre_grafico` que acepte `ruta_png=None`.
# 3. **Dos rondas.** Reflexioná sobre el PNG V2 y generá una V3. Compará las tres
#    imágenes una al lado de la otra. ¿La tercera mejora o solo cambia?
# 4. **Rúbrica visual.** Pedile al crítico puntuaciones de 1 a 5 en legibilidad,
#    fidelidad a la instrucción y honestidad con los datos, además del feedback.
# 5. **Modelo barato para criticar.** Probá `model_reflexion=MODEL_CHEAP` (también ve
#    imágenes). ¿Qué pierde la crítica?

# %% [markdown]
# ## Para cerrar
#
# - El patrón es el mismo de los labs 01 y 02: generar → mirar el resultado → corregir.
#   Lo que cambia es **qué** mira el crítico: texto, una tabla, una imagen.
# - Cada paso que parsea la salida del modelo tiene que fallar **fuerte y claro**
#   cuando la salida no tiene la forma esperada. Un `if match:` que sigue adelante es
#   un bug que se disfraza de robustez.
# - La reflexión ve lo que le mostrás. Si el problema está en los datos y no en el
#   gráfico, hay que darle los datos. Saber qué información necesita el crítico es
#   parte del diseño del agente.

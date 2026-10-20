# %% [markdown]
# # Reflexión sobre un ensayo: borrador → crítica → revisión
# **Módulo 2 · Lab 01.** Un flujo de tres llamadas al LLM donde el modelo escribe un
# ensayo, lo critica y lo reescribe usando esa crítica.
#
# ## Objetivos
# Al terminar vas a poder:
# - Hacer una llamada a un LLM con `aisuite` y quedarte solo con el texto de la respuesta.
# - Encadenar llamadas: la salida de una es la entrada de la siguiente.
# - Explicar qué es el patrón de **reflexión** y por qué se hace en pasos separados.
# - Armar un bucle de N rondas de crítica + revisión y guardar las versiones intermedias.
#
# > Lo que se evalúa es el **código**: que cada función llame al modelo, devuelva el
# > tipo correcto y pase bien los datos entre pasos. No se evalúa la calidad del ensayo.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. Cuando llamás a un LLM por API, ¿qué viaja en el parámetro `messages`?
#    a) Solo el último mensaje del usuario. b) La lista completa de mensajes, cada uno con su rol. c) El nombre del modelo.
# 2. Si mandás dos veces exactamente el mismo prompt, ¿qué pasa?
#    a) Devuelve siempre el mismo texto. b) Puede devolver textos distintos. c) La segunda vez falla porque está en caché.
# 3. En el patrón de reflexión, ¿qué recibe como entrada el paso de **revisión**?
#    a) Solo la consigna original. b) El borrador y la crítica. c) Solo la crítica.
# 4. ¿Por qué la crítica se pide en una llamada separada en vez de escribir "redactá y después mejorá" en un solo prompt?
#    a) Porque es más barato. b) Porque el modelo tiene que recibir el borrador terminado como entrada para evaluarlo, igual que un revisor humano. c) Porque la API no acepta prompts largos.
# 5. Python: tenés `def f(x, model=AI_STRONG)`. ¿Qué pasa si llamás `f("hola")`?
#    a) Error, falta `model`. b) `model` toma el valor de `AI_STRONG`. c) `model` queda en `None`.

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (la API no tiene memoria: todo el contexto va en `messages`),
# 2-b (la generación es estocástica; con `temperature=0` se reduce pero no se garantiza),
# 3-b (sin el borrador no hay qué revisar; sin la crítica no hay guía),
# 4-b (reflexionar es evaluar un artefacto terminado; en un solo prompt el modelo no "ve" su propio texto completo antes de criticarlo),
# 5-b (parámetro con valor por defecto; `AI_STRONG` se evalúa cuando se define la función).

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
AI_CHEAP = f"openai:{MODEL_CHEAP}"      # aisuite pide el proveedor como prefijo: "openai:gpt-4.1-mini"
AI_STRONG = f"openai:{MODEL_STRONG}"

from utils import mostrar_caja, contar_palabras, resumen_versiones, COLORES

print("Modelo barato:", AI_CHEAP)
print("Modelo fuerte:", AI_STRONG)

# %% [markdown]
# ## 1. Teoría breve: qué es reflexionar
#
# **Para qué.** Un LLM que responde "de una" (one-shot) comete errores que él mismo
# detectaría si le mostraran su texto terminado. La reflexión aprovecha eso: el modelo
# produce un borrador, después *lee* ese borrador como si fuera de otra persona y lo
# critica, y por último lo reescribe siguiendo la crítica.
#
# **Por qué así (en pasos separados).** Criticar y escribir son tareas distintas. Si
# pedís las dos en un solo prompt, el modelo tiende a mezclar y a ser condescendiente
# con lo que acaba de escribir. Separarlas te da tres ventajas: cada prompt es más
# simple, podés usar un modelo distinto para criticar, y te quedás con las versiones
# intermedias para comparar.
#
# **Ejemplo.** Es lo que hace cualquier persona que escribe bien: borrador, lo dejás
# enfriar, lo leés con ojo crítico, lo corregís.
#
# ```
# Consigna ──► Borrador (V1) ──► Crítica ──► Revisión (V2)
#                                  ▲             │
#                                  └── (opcional: repetir N rondas) ◄──┘
# ```
#
# ```mermaid
# flowchart LR
#   P[Consigna] --> G[generar_borrador → V1]
#   G --> C[reflexionar_sobre_borrador → crítica]
#   C --> R[revisar_borrador V1 + crítica → V2]
#   R -. rondas .-> C
# ```
#
# Cada caja del diagrama va a ser una función. Las tres hacen lo mismo por dentro
# (una llamada al modelo); lo que cambia es **qué le mandan** y **qué devuelven**.

# %% [markdown]
# ## 2. Ejemplo resuelto: la forma de una llamada
#
# Esta función está completa. Mirala con atención porque las tres funciones que siguen
# repiten exactamente esta forma:
#
# - `client.chat.completions.create(model=..., messages=[...])` hace la llamada.
# - `messages` es una lista de diccionarios con `role` y `content`.
# - La respuesta es un objeto; el texto está en `response.choices[0].message.content`.

# %%
def preguntar(mensaje: str, model: str = AI_CHEAP) -> str:
    """Manda un único mensaje de usuario al modelo y devuelve el texto de la respuesta."""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": mensaje}],
    )
    return response.choices[0].message.content


# %%
# Prueba rápida (una llamada corta y barata)
texto = preguntar("Explicá en una oración qué es un ensayo.")
print(type(texto))
print(texto)

# %% [markdown]
# ## 3. Paso 1: generar el borrador
#
# `generar_borrador` recibe la consigna del ensayo y devuelve el texto del borrador.
# La instrucción ya está armada; vos tenés que hacer la llamada y devolver **solo el
# texto** (no el objeto `response` entero).
#
# Fijate que `model` tiene como valor por defecto `AI_STRONG`: nunca escribimos el
# nombre de un modelo adentro de la función.

# %%
def generar_borrador(prompt: str, model: str = AI_STRONG) -> str:
    """Genera un borrador de ensayo (introducción, desarrollo, conclusión) a partir de una consigna.

    Args:
        prompt: la consigna o pregunta del ensayo.
        model: modelo a usar, en formato aisuite ("openai:...").

    Returns:
        El texto del borrador.
    """
    instruccion = f"""Escribí un borrador de ensayo bien estructurado que responda a la siguiente consigna.
El borrador tiene que tener introducción, desarrollo y conclusión, y entre 300 y 400 palabras.
Devolvé solo el ensayo, sin comentarios adicionales.

Consigna:
{prompt}
"""
    # Hacé la llamada al modelo con `instruccion` y devolvé el texto de la respuesta
    ### BEGIN SOLUTION
    ### STUDENT: # Pista: es igual que preguntar(), pero el mensaje es `instruccion` y el modelo es `model`.
    ### STUDENT: raise NotImplementedError("Completá esta función")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruccion}],
    )
    return response.choices[0].message.content
    ### END SOLUTION


# %%
# Prueba rápida
consigna = "¿Las redes sociales deberían estar reguladas por el Estado?"

borrador = generar_borrador(consigna)
print(type(borrador), "-", contar_palabras(borrador), "palabras")
mostrar_caja("Paso 1 – Borrador (V1)", borrador, COLORES["borrador"])

# %% [markdown]
# ## 4. Paso 2: criticar el borrador
#
# `reflexionar_sobre_borrador` recibe el **texto** del borrador (no la consigna) y
# devuelve una crítica en prosa. Acá hay dos cosas para completar:
#
# 1. **La instrucción.** Tenés que pedirle al modelo que critique el borrador de forma
#    constructiva. Cubrí al menos: estructura, claridad, fuerza de los argumentos y
#    estilo. Pedile que **no** reescriba el ensayo: solo que lo evalúe.
# 2. **La llamada**, igual que antes.
#
# Un buen prompt de crítica le da al modelo un rol ("sos un editor exigente") y le pide
# que señale problemas concretos, no elogios genéricos.

# %%
def reflexionar_sobre_borrador(borrador: str, model: str = AI_STRONG) -> str:
    """Pide una crítica constructiva del borrador. No reescribe el ensayo.

    Args:
        borrador: el texto del ensayo a evaluar.
        model: modelo a usar, en formato aisuite.

    Returns:
        La crítica, en párrafos.
    """
    # Paso 1: armar la instrucción. Tiene que incluir el borrador y pedir crítica, no reescritura.
    ### BEGIN SOLUTION
    ### STUDENT: instruccion = f"""..."""  # Completá: rol de editor, qué evaluar, "no reescribas", y el {borrador}
    instruccion = f"""Sos un editor exigente. Leé el siguiente borrador de ensayo y hacé una crítica constructiva.
Señalá problemas concretos de estructura, claridad, fuerza de los argumentos y estilo,
y sugerí cómo mejorarlos. No reescribas el ensayo: solo evaluá. Respondé en párrafos.

Borrador:
{borrador}
"""
    ### END SOLUTION
    # Paso 2: llamar al modelo y devolver el texto de la respuesta
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruccion}],
    )
    return response.choices[0].message.content
    ### END SOLUTION


# %%
# Prueba rápida: la crítica se hace sobre el borrador del paso anterior
critica = reflexionar_sobre_borrador(borrador)
print(type(critica), "-", contar_palabras(critica), "palabras")
mostrar_caja("Paso 2 – Crítica", critica, COLORES["critica"])

# %% [markdown]
# ## 5. Paso 3: revisar el borrador con la crítica
#
# `revisar_borrador` es el paso que **combina** los dos anteriores: recibe el borrador
# y la crítica, y devuelve una versión mejorada. Lo importante es que la instrucción
# incluya **los dos textos**: si le mandás solo la crítica, el modelo no tiene qué
# revisar; si le mandás solo el borrador, no sabe qué cambiar.
#
# Pedile que devuelva **solo el ensayo revisado**, sin explicar los cambios (eso te va a
# servir después para encadenar rondas sin que se acumulen comentarios).

# %%
def revisar_borrador(borrador: str, critica: str, model: str = AI_STRONG) -> str:
    """Reescribe el borrador aplicando la crítica. Devuelve solo el ensayo revisado.

    Args:
        borrador: versión actual del ensayo.
        critica: la crítica producida por reflexionar_sobre_borrador.
        model: modelo a usar, en formato aisuite.

    Returns:
        El ensayo revisado.
    """
    # Paso 1: armar la instrucción con el borrador Y la crítica
    ### BEGIN SOLUTION
    ### STUDENT: instruccion = f"""..."""  # Completá: incluí {borrador} y {critica}, y pedí solo el ensayo revisado
    instruccion = f"""Revisá el siguiente borrador de ensayo aplicando la crítica que lo acompaña.
Mejorá claridad, coherencia, argumentación y fluidez. Mantené la extensión (300 a 400 palabras).
Devolvé únicamente el ensayo revisado, sin comentarios ni lista de cambios.

Borrador original:
{borrador}

Crítica:
{critica}
"""
    ### END SOLUTION
    # Paso 2: llamar al modelo y devolver el texto (podés reusar preguntar() si querés)
    ### BEGIN SOLUTION
    return preguntar(instruccion, model=model)
    ### END SOLUTION


# %%
# Prueba rápida
revision = revisar_borrador(borrador, critica)
print(type(revision), "-", contar_palabras(revision), "palabras")
mostrar_caja("Paso 3 – Revisión (V2)", revision, COLORES["revision"])

# %% [markdown]
# ## 6. Comparar las versiones
#
# Ahora tenés las tres piezas. Mirá las dos versiones una al lado de la otra y
# preguntate: ¿la V2 responde a lo que pedía la crítica? ¿Cambió algo que la crítica no
# mencionaba? ¿Se hizo más larga sin necesidad?

# %%
print(resumen_versiones([borrador, revision]))
print("¿La revisión es distinta del borrador?", revision.strip() != borrador.strip())

mostrar_caja("V1 – Borrador", borrador, COLORES["borrador"])
mostrar_caja("Crítica", critica, COLORES["critica"])
mostrar_caja("V2 – Revisión", revision, COLORES["revision"])

# %% [markdown]
# ## 7. Combinar: N rondas de reflexión
#
# Una ronda suele alcanzar. Pero el patrón es un **bucle**: podés criticar la V2,
# revisarla a V3, y así. `reflexionar_en_bucle` encadena todo y devuelve un diccionario
# con las listas de borradores y críticas, para que después puedas inspeccionar cada
# paso.
#
# Estructura esperada del resultado con `rondas=2`:
#
# ```python
# {
#   "borradores": [V1, V2, V3],   # rondas + 1 textos
#   "criticas":   [c1, c2],       # rondas textos
# }
# ```
#
# Cuidado con una trampa clásica: en cada vuelta hay que criticar y revisar el **último**
# borrador, no el primero.

# %%
def reflexionar_en_bucle(prompt: str, rondas: int = 2, model: str = AI_STRONG) -> dict:
    """Genera un borrador y lo pasa por N rondas de crítica + revisión.

    Args:
        prompt: la consigna del ensayo.
        rondas: cuántas veces criticar y revisar.
        model: modelo a usar en los tres pasos.

    Returns:
        {"borradores": [V1, V2, ...], "criticas": [c1, c2, ...]}
    """
    borradores = []
    criticas = []

    # Paso 1: generar el primer borrador y guardarlo en `borradores`
    ### BEGIN SOLUTION
    actual = generar_borrador(prompt, model=model)
    borradores.append(actual)
    ### END SOLUTION

    # Paso 2: por cada ronda, criticar el borrador actual, revisarlo, y guardar crítica y nueva versión
    ### BEGIN SOLUTION
    for _ in range(rondas):
        critica = reflexionar_sobre_borrador(actual, model=model)
        actual = revisar_borrador(actual, critica, model=model)
        criticas.append(critica)
        borradores.append(actual)
    ### END SOLUTION

    return {"borradores": borradores, "criticas": criticas}


# %%
# Prueba rápida: 2 rondas = 5 llamadas al modelo (1 + 2 × 2). Tarda un rato.
resultado = reflexionar_en_bucle("¿Debería ser obligatorio aprender a programar en la escuela secundaria?", rondas=2)

print("Borradores:", len(resultado["borradores"]), "| Críticas:", len(resultado["criticas"]))
print(resumen_versiones(resultado["borradores"]))
mostrar_caja("Versión final (V3)", resultado["borradores"][-1], COLORES["revision"])

# %% [markdown]
# ## 8. Verificación automática
#
# `tests.py` tiene dos grupos de chequeos:
#
# - **Estructurales (sin API):** usan un `FakeClient` que imita la forma de la respuesta
#   de aisuite y registra qué prompt recibió. Verifican que tus funciones devuelven
#   `str`, que usan el `model` que les pasan, que `revisar_borrador` recibe el borrador
#   **y** la crítica, y que la revisión es la salida del modelo (no el borrador de entrada).
# - **De integración (requiere API):** corren el flujo completo con el cliente real.
#
# Si pasás `client=None` solo corren los estructurales.

# %%
from tests import run_all

run_all(
    generar_borrador,
    reflexionar_sobre_borrador,
    revisar_borrador,
    reflexionar_en_bucle=reflexionar_en_bucle,
    client=client,          # poné None para saltear los tests que llaman a la API
)

# %% [markdown]
# ## 9. Si te sobra tiempo
#
# Consignas abiertas (no hay solución en este notebook; ideas en el workbook):
#
# 1. **Crítico barato, escritor fuerte (o al revés).** Corré el flujo con `AI_CHEAP` para
#    criticar y `AI_STRONG` para escribir, y después invertilo. ¿Dónde se nota más la
#    diferencia de modelo?
# 2. **Crítica con rúbrica.** Cambiá el prompt de `reflexionar_sobre_borrador` para que
#    devuelva una puntuación de 1 a 5 en cuatro criterios antes de la prosa. ¿La revisión
#    mejora más cuando la crítica es más estructurada?
# 3. **Condición de corte.** Modificá `reflexionar_en_bucle` para que se detenga antes de
#    agotar las rondas si la crítica dice que el ensayo ya está bien (por ejemplo, si
#    contiene la palabra "APROBADO" que vos le pediste que use en ese caso).
# 4. **Medir.** Para 3 consignas distintas, anotá las palabras de V1, V2 y V3. ¿Las
#    revisiones tienden a alargar el texto? ¿Es eso una mejora?

# %% [markdown]
# ## Para cerrar
#
# - La reflexión no es magia: son **tres prompts** y pasar bien los datos entre ellos.
# - El paso de revisión necesita **las dos entradas**. Si una falta, el patrón se rompe
#   en silencio (el modelo igual devuelve algo).
# - La crítica "en papel" tiene un límite: el modelo solo ve el texto. En el próximo lab
#   vamos a darle **feedback externo** (el resultado real de ejecutar lo que generó).

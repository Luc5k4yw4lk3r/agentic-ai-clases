# %% [markdown]
# # Evaluar un componente: ¿de dónde saca las fuentes el agente?
# **Módulo 4 · Lab 01.** Construís una evaluación objetiva y barata para UN paso del
# agente de investigación (la búsqueda de referencias), sin correr todo el pipeline.
#
# ## Objetivos
# Al terminar vas a poder:
# - Explicar qué es una evaluación *a nivel de componente* y cuándo conviene usarla.
# - Separar el paso de búsqueda del resto del flujo para medirlo solo.
# - Extraer URLs de un texto libre y clasificarlas por dominio sin falsos positivos.
# - Armar un mini *gold standard* (temas + dominios confiables) y correrlo varias veces.
# - Leer una tabla de resultados y decidir si el componente mejora o no.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. **(Repaso M3)** En *function calling*, ¿quién ejecuta la tool cuando el modelo pide llamarla?
#    a) El modelo, dentro de OpenAI. b) Tu código Python. c) El navegador.
# 2. **(Repaso M3)** ¿Qué limita `max_turns=5` en `aisuite`?
#    a) La cantidad de resultados que devuelve cada tool. b) La cantidad de vueltas del loop
#    modelo → tool → modelo. c) La cantidad de reintentos si la API falla.
# 3. **(Nuevo)** ¿Por qué conviene evaluar solo el paso de búsqueda en vez de todo el pipeline?
#    a) Porque el resto del pipeline no tiene errores. b) Porque es más barato y la señal no se
#    mezcla con la aleatoriedad de los pasos siguientes. c) Porque los LLM no se pueden evaluar.
# 4. **(Nuevo)** "Porcentaje de URLs que caen en dominios confiables" es una evaluación...
#    a) Subjetiva, sin ground truth. b) Objetiva, con ground truth por ejemplo.
#    c) Objetiva, pero sin ground truth.
# 5. **(Base Python)** ¿Qué devuelve `"mit.edu" in "summit.edu"`?
#    a) `False`, porque son dominios distintos. b) `True`, porque `in` busca substrings.
#    c) Da error porque no son listas.

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (el modelo solo devuelve el nombre y los argumentos; tu código
# ejecuta la función y le devuelve el resultado), 2-b (cada vuelta es una llamada al modelo que
# puede pedir tools; aisuite corta a las 5), 3-b (es la idea central de la clase: señal más
# limpia y más barata), 4-b (hay una regla objetiva y una lista de dominios definida para cada
# tema), 5-b (y por eso el chequeo por substring del original tenía falsos positivos).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import os
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

import aisuite as ai

client = ai.Client()
AI_CHEAP = f"openai:{MODEL_CHEAP}"
AI_STRONG = f"openai:{MODEL_STRONG}"

import research_tools   # tools compartidas: arXiv, Wikipedia, Tavily (con fallback a Wikipedia)
import utils            # mostrar_markdown, mostrar_texto, mostrar_evaluacion

print("Modelos:", AI_CHEAP, "|", AI_STRONG)
print("Tavily:", "configurado" if os.getenv("TAVILY_API_KEY", "").startswith("tvly-") and "..." not in os.getenv("TAVILY_API_KEY", "") else "sin key (fallback a Wikipedia)")

# %% [markdown]
# ## 1. Teoría breve: evaluar un componente, no todo el pipeline
#
# **Para qué.** En M3 armaste un agente que (1) busca en la web, (2) reflexiona y (3) publica un
# reporte. Si el reporte sale malo, ¿qué paso falló? Correr todo el flujo cada vez que cambiás
# algo cuesta plata y tiempo, y la aleatoriedad de los pasos 2 y 3 tapa las mejoras del paso 1.
#
# **Por qué así.** La solución es medir cada componente por separado con una métrica que se
# calcule con código. Para el paso de búsqueda, una métrica razonable es: *¿qué porcentaje de las
# URLs que trajo el agente pertenece a dominios en los que confiamos para ese tema?*
#
# Esa métrica cae en el cuadrante **objetiva + con ground truth por ejemplo**:
#
# | | Con ground truth por ejemplo | Sin ground truth |
# |---|---|---|
# | **Objetiva (código)** | porcentaje de URLs confiables **(acá)** | cantidad de URLs devueltas |
# | **Subjetiva (LLM juez)** | comparar con un reporte modelo | "¿qué tan bien escrito está?" |
#
# **Ejemplo práctico.** Para el tema "agujeros negros" definimos que confiamos en `arxiv.org`,
# `nasa.gov` y `nature.com`. Si el agente trae 5 URLs y 3 son de esos dominios, el ratio es 0,6.
# Con umbral 0,4 → PASS. Si el mes que viene cambiamos el prompt y el ratio baja a 0,2 → FAIL:
# detectamos la regresión sin leer ni un reporte.
#
# **Lo que vas a construir.** Cinco funciones chicas, cada una con un hueco:
# `extraer_urls` → `dominio_de` → `es_dominio_confiable` → `evaluar_referencias` →
# `correr_evaluacion`. Las cuatro primeras son puras (sin API) y tienen tests. La última llama
# al agente sobre un mini gold standard de 5 temas.

# %% [markdown]
# ## 2. El componente a evaluar: `buscar_referencias`
#
# Esta función ya viene resuelta. Es el paso de búsqueda del agente de M3, pero aislado: solo
# busca y lista referencias, no escribe ni reflexiona. Dos detalles:
#
# - Usa `aisuite`, que ejecuta el loop de tools por nosotros (`max_turns=5`).
# - Le pasamos la **fecha de hoy** en el prompt: sin eso el modelo cree que está en su fecha de
#   entrenamiento y pide "lo más reciente" de hace dos años.
#
# Las consultas a las tools van en inglés (arXiv y la Wikipedia en inglés tienen mucha más
# cobertura), pero el prompt está en español para que lo puedas leer y modificar.

# %%
def buscar_referencias(tema: str, model: str = AI_CHEAP) -> str:
    """Busca referencias sobre `tema` usando arXiv, Tavily y Wikipedia. Devuelve Markdown con URLs.

    Si una tool o el modelo fallan, devuelve un texto que empieza con "[Error" en lugar de
    levantar la excepción: para la evaluación, una búsqueda que falla es un FAIL del
    componente, no un motivo para frenar toda la corrida.
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""Sos una función de investigación. Tenés tres tools:
- arxiv_search_tool: papers académicos.
- tavily_search_tool: búsqueda web general.
- wikipedia_search_tool: resúmenes enciclopédicos.

Tarea: encontrá entre 3 y 5 referencias confiables sobre el tema "{tema}".
Hacé las consultas a las tools en inglés (arXiv y Wikipedia en inglés tienen mucha más cobertura).
Devolvé una lista en Markdown con un ítem por referencia: título, fuente y la URL completa
(empezando con http). No inventes URLs: usá solo las que devolvieron las tools.

Hoy es {hoy}."""

    tools = [
        research_tools.arxiv_search_tool,
        research_tools.tavily_search_tool,
        research_tools.wikipedia_search_tool,
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice="auto",
            max_turns=5,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"[Error en la búsqueda: {e}]"

# %%
# Prueba rápida (requiere API): ~1 llamada al modelo + 1 a 4 llamadas a tools
texto_prueba = buscar_referencias("recent developments in black hole science")
utils.mostrar_markdown(texto_prueba, titulo="Referencias encontradas")

# %% [markdown]
# ## 3. Construir la evaluación paso a paso
#
# ### Ejemplo resuelto: las tres herramientas de Python que vas a usar
#
# Antes de los huecos, mirá cómo se comportan `re.findall`, `urlparse` y `endswith`. El tercer
# print muestra **el bug del material original**: comparaba dominios con `in`, que busca
# substrings, así que `summit.edu` pasaba como si fuera `mit.edu`.

# %%
import re
from urllib.parse import urlparse

ejemplo = "Ver https://www.nature.com/articles/abc (y también https://arxiv.org/abs/2301.00001)."

print("1) re.findall encuentra todo lo que empieza con http:// o https://")
print("   ", re.findall(r"https?://[^\s<>\"'\]\)]+", ejemplo))

print("2) urlparse separa la URL en partes; netloc es el host")
print("   ", urlparse("https://www.nature.com/articles/abc").netloc)

print("3) El bug del original: comparar dominios con `in`")
print("   'mit.edu' in 'summit.edu' ->", "mit.edu" in "summit.edu", " (falso positivo)")
print("   'summit.edu'.endswith('.mit.edu') ->", "summit.edu".endswith(".mit.edu"), " (correcto)")
print("   'web.mit.edu'.endswith('.mit.edu') ->", "web.mit.edu".endswith(".mit.edu"), " (subdominio legítimo)")

# %% [markdown]
# ### 3.1 `extraer_urls`: del texto libre a una lista de URLs
#
# El modelo devuelve Markdown: a veces `[título](url)`, a veces la URL pelada, a veces entre
# paréntesis o con un punto al final. Queremos una lista limpia, **sin duplicados y en el orden
# en que aparecen** (el orden importa para leer el detalle después).
#
# Pista para el paso 1: la expresión regular del ejemplo resuelto excluye espacios, `<`, `>`,
# comillas, `]` y `)` para no "tragarse" el cierre de un link de Markdown.

# %%
def extraer_urls(texto: str) -> list[str]:
    """Devuelve las URLs (http/https) que aparecen en `texto`, sin duplicados y en orden de aparición."""
    # Paso 1: encontrar todas las candidatas con una expresión regular
    ### BEGIN SOLUTION
    ### STUDENT: candidatas = []  # Pista: re.findall(r"https?://[^\s<>\"'\]\)]+", texto)
    candidatas = re.findall(r"https?://[^\s<>\"'\]\)]+", texto)
    ### END SOLUTION

    # Paso 2: sacar la puntuación que suele quedar pegada al final (".", ",", ";", ":", "!", "?")
    limpias = []
    for url in candidatas:
        ### BEGIN SOLUTION
        ### STUDENT: limpias.append(url)  # Pista: url.rstrip(".,;:!?")
        limpias.append(url.rstrip(".,;:!?"))
        ### END SOLUTION

    # Paso 3: eliminar duplicados conservando el orden (un set desordena; usá una lista y `in`)
    urls = []
    ### BEGIN SOLUTION
    for url in limpias:
        if url not in urls:
            urls.append(url)
    ### END SOLUTION
    return urls

# %%
# Prueba rápida (sin API)
texto_ejemplo = """
- Transformer (Wikipedia): https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)
- [Attention is all you need](https://arxiv.org/abs/1706.03762).
- Repetida: https://arxiv.org/abs/1706.03762
- Blog: https://towardsdatascience.com/some-post, y nada más.
"""
for u in extraer_urls(texto_ejemplo):
    print(u)
print("Esperado: 3 URLs distintas, la de arXiv una sola vez y sin el punto final.")

# %% [markdown]
# ### 3.2 `dominio_de`: quedarnos solo con el host
#
# Para comparar contra la lista de confiables no queremos la URL completa sino el dominio:
# `https://www.nature.com/articles/abc` → `nature.com`. Usá `urlparse(url).netloc`, pasalo a
# minúsculas y sacale el prefijo `www.` si lo tiene. No saques otros subdominios:
# `en.wikipedia.org` tiene que quedar como está (lo resolvemos en la función siguiente).

# %%
def dominio_de(url: str) -> str:
    """Devuelve el dominio de `url` en minúsculas y sin el prefijo "www.". Ej: "https://www.Nature.com/x" -> "nature.com"."""
    # Paso 1: extraer el host con urlparse y pasarlo a minúsculas
    ### BEGIN SOLUTION
    ### STUDENT: host = ""  # Pista: urlparse(url).netloc.lower()
    host = urlparse(url).netloc.lower()
    ### END SOLUTION
    # Paso 2: sacar el prefijo "www." si está (solo ese prefijo, nada más)
    ### BEGIN SOLUTION
    if host.startswith("www."):
        host = host[len("www."):]
    ### END SOLUTION
    return host

# %%
# Prueba rápida (sin API)
for u in ["https://www.nature.com/articles/abc", "http://arxiv.org/abs/1706.03762",
          "https://en.wikipedia.org/wiki/Black_hole", "https://WWW.NASA.GOV/mission"]:
    print(f"{u:50s} -> {dominio_de(u)}")

# %% [markdown]
# ### 3.3 `es_dominio_confiable`: coincidencia exacta o por sufijo con punto
#
# Acá corregimos el bug del original. Un dominio es confiable si:
# - es **exactamente** uno de la lista (`"arxiv.org" == "arxiv.org"`), o
# - termina en **punto + dominio de la lista** (`"en.wikipedia.org".endswith(".wikipedia.org")`).
#
# Así `summit.edu` ya no pasa por `mit.edu`, pero `web.mit.edu` sí. Y `arxiv.org.evil.com`
# tampoco pasa, porque no *termina* en `arxiv.org`.

# %%
def es_dominio_confiable(dominio: str, confiables: set[str]) -> bool:
    """True si `dominio` es uno de `confiables` o un subdominio de alguno (sufijo con punto)."""
    dominio = dominio.lower()
    for confiable in confiables:
        confiable = confiable.lower()
        ### BEGIN SOLUTION
        ### STUDENT: pass  # Pista: dos condiciones unidas con `or`; si alguna se cumple, return True
        if dominio == confiable or dominio.endswith("." + confiable):
            return True
        ### END SOLUTION
    return False

# %%
# Prueba rápida (sin API): las dos últimas líneas son los falsos positivos del original
CONFIABLES_DEMO = {"arxiv.org", "wikipedia.org", "mit.edu", "nature.com"}
for d in ["arxiv.org", "en.wikipedia.org", "web.mit.edu", "summit.edu", "arxiv.org.evil.com"]:
    print(f"{d:22s} -> {es_dominio_confiable(d, CONFIABLES_DEMO)}")

# %% [markdown]
# ### 3.4 `evaluar_referencias`: juntar todo en una métrica con PASS/FAIL
#
# Combina las tres funciones anteriores. Devuelve un `dict` con:
#
# | clave | tipo | qué es |
# |---|---|---|
# | `total` | int | cantidad de URLs distintas encontradas |
# | `confiables` | int | cuántas caen en dominios confiables |
# | `ratio` | float | `confiables / total` (0.0 si no hay URLs) |
# | `aprobado` | bool | `ratio >= umbral` **y** `total > 0` |
# | `detalle` | list | una tupla `(url, dominio, ok)` por URL, en orden |
#
# Ojo con el caso borde: si el texto no tiene URLs, el ratio es 0.0 y **no** aprueba (un
# agente que no cita nada no puede pasar la evaluación). Y no dividas por cero.

# %%
def evaluar_referencias(texto: str, confiables: set[str], umbral: float = 0.4) -> dict:
    """Evalúa qué proporción de las URLs en `texto` pertenece a `confiables`.

    Devuelve un dict con las claves total, confiables (cantidad), ratio, aprobado y detalle.
    """
    urls = extraer_urls(texto)

    # Paso 1: clasificar cada URL y armar `detalle` como lista de tuplas (url, dominio, ok)
    detalle = []
    cantidad_confiables = 0
    for url in urls:
        ### BEGIN SOLUTION
        ### STUDENT: dominio = ""      # Pista: dominio_de(url)
        ### STUDENT: ok = False        # Pista: es_dominio_confiable(dominio, confiables)
        dominio = dominio_de(url)
        ok = es_dominio_confiable(dominio, confiables)
        ### END SOLUTION
        detalle.append((url, dominio, ok))
        if ok:
            cantidad_confiables += 1

    # Paso 2: calcular ratio (sin dividir por cero) y decidir si aprueba
    ### BEGIN SOLUTION
    ### STUDENT: ratio = 0.0
    ### STUDENT: aprobado = False
    total = len(urls)
    if total == 0:
        ratio = 0.0
    else:
        ratio = cantidad_confiables / total
    aprobado = total > 0 and ratio >= umbral
    ### END SOLUTION

    return {
        "total": len(urls),
        "confiables": cantidad_confiables,
        "ratio": ratio,
        "aprobado": aprobado,
        "detalle": detalle,
    }

# %%
# Prueba rápida (sin API) con el texto de ejemplo de 3.1: 2 de 3 confiables -> ratio 0.67 -> PASS
resultado_demo = evaluar_referencias(texto_ejemplo, {"arxiv.org", "wikipedia.org"}, umbral=0.4)
utils.mostrar_evaluacion(resultado_demo, umbral=0.4, titulo="Evaluación del texto de ejemplo")

# %%
# Chequeo automático de las cuatro funciones puras (sin API)
from tests import run_all

run_all(extraer_urls, dominio_de, es_dominio_confiable, evaluar_referencias)

# %% [markdown]
# ### 3.5 Evaluar la búsqueda real
#
# Ahora sí: aplicamos la evaluación al texto que devolvió `buscar_referencias` al principio.
# Esta es la misma lógica que el material original, pero sin falsos positivos ni URLs
# duplicadas infladas en el total.

# %%
# Requiere haber corrido la celda de prueba de buscar_referencias (sección 2)
CONFIABLES_AGUJEROS_NEGROS = {"arxiv.org", "nasa.gov", "nature.com", "science.org", "wikipedia.org", "eso.org", "esa.int"}
resultado_real = evaluar_referencias(texto_prueba, CONFIABLES_AGUJEROS_NEGROS, umbral=0.4)
utils.mostrar_evaluacion(resultado_real, umbral=0.4, titulo="Agujeros negros: fuentes del agente")

# %% [markdown]
# ## 4. Un mini gold standard y una corrida de evaluación
#
# Un solo tema no alcanza para saber si el componente es bueno. Armamos un **gold standard**
# chico: 5 temas, cada uno con su propia lista de dominios confiables (el ground truth depende
# del tema: para biomedicina confiamos en `nih.gov`, para física en `arxiv.org` y `aps.org`).
#
# Los temas están en inglés porque son la consulta que va a las tools. Revisá las listas: son
# una propuesta, no una verdad absoluta. Discutir qué dominios entran es parte del trabajo de
# evaluación.

# %%
CASOS = [
    {
        "tema": "retrieval-augmented generation for large language models",
        "confiables": {"arxiv.org", "acm.org", "openreview.net", "aclanthology.org", "wikipedia.org"},
    },
    {
        "tema": "CRISPR gene editing recent clinical trials",
        "confiables": {"nih.gov", "nature.com", "science.org", "cell.com", "nejm.org", "wikipedia.org"},
    },
    {
        "tema": "recent developments in black hole science",
        "confiables": {"arxiv.org", "nasa.gov", "nature.com", "science.org", "eso.org", "esa.int", "wikipedia.org"},
    },
    {
        "tema": "transformer architecture and the attention mechanism",
        "confiables": {"arxiv.org", "neurips.cc", "acm.org", "ieee.org", "wikipedia.org"},
    },
    {
        "tema": "quantum error correction with surface codes",
        "confiables": {"arxiv.org", "nature.com", "aps.org", "ieee.org", "wikipedia.org"},
    },
]
print(f"{len(CASOS)} casos en el gold standard")

# %% [markdown]
# ### 4.1 `correr_evaluacion`: una fila por tema y repetición
#
# Recorre los casos, llama a `buscar_referencias` (esto cuesta: una llamada al modelo más las
# tools por cada fila) y evalúa. Devuelve un `DataFrame` con las columnas `tema`, `repeticion`,
# `total`, `confiables`, `ratio`, `aprobado`. Si `repeticiones > 1`, cada tema se corre varias
# veces: lo vas a usar en la extensión para ver cuánto varía el resultado entre corridas.

# %%
def correr_evaluacion(casos: list[dict], repeticiones: int = 1, umbral: float = 0.4,
                      model: str = AI_CHEAP) -> pd.DataFrame:
    """Corre buscar_referencias + evaluar_referencias para cada caso (y repetición) y devuelve un DataFrame."""
    filas = []
    for caso in casos:
        for repeticion in range(1, repeticiones + 1):
            # Paso 1: buscar y evaluar este caso
            ### BEGIN SOLUTION
            ### STUDENT: texto = ""          # Pista: buscar_referencias(caso["tema"], model=model)
            ### STUDENT: resultado = {}      # Pista: evaluar_referencias(texto, caso["confiables"], umbral)
            texto = buscar_referencias(caso["tema"], model=model)
            resultado = evaluar_referencias(texto, caso["confiables"], umbral=umbral)
            ### END SOLUTION

            # Paso 2: armar la fila con las columnas pedidas y agregarla a `filas`
            ### BEGIN SOLUTION
            filas.append(
                {
                    "tema": caso["tema"],
                    "repeticion": repeticion,
                    "total": resultado["total"],
                    "confiables": resultado["confiables"],
                    "ratio": round(resultado["ratio"], 2),
                    "aprobado": resultado["aprobado"],
                }
            )
            ### END SOLUTION
            print(f"[{repeticion}/{repeticiones}] {caso['tema'][:45]:45s} ratio={resultado['ratio']:.2f} "
                  f"{'PASS' if resultado['aprobado'] else 'FAIL'}")
    return pd.DataFrame(filas)

# %%
# Prueba rápida (requiere API): 5 filas = 5 llamadas al modelo con sus tools (1 a 2 minutos)
df = correr_evaluacion(CASOS, repeticiones=1)
display(df)
print(f"Aprobados: {int(df['aprobado'].sum())} de {len(df)}  |  ratio promedio: {df['ratio'].mean():.2f}")

# %% [markdown]
# ## 5. Si te sobra tiempo
#
# Consignas abiertas, sin huecos (las soluciones esbozadas están en la guía docente):
#
# 1. **Varianza entre corridas.** Corré `correr_evaluacion(CASOS, repeticiones=3)` y mirá
#    `df.groupby("tema")[["ratio", "aprobado"]].agg(["mean", "std"])`. ¿Hay temas que a veces
#    aprueban y a veces no? ¿Qué te dice eso sobre confiar en una sola corrida?
# 2. **Ajustar el umbral.** Con el mismo `df` (no vuelvas a llamar a la API), recalculá
#    `aprobado` para umbrales 0.3, 0.5 y 0.7: `df["ratio"] >= 0.5`. ¿Cuál elegirías y por qué?
# 3. **Agregar un tema.** Sumá un sexto caso a `CASOS` sobre un tema que te interese y definí sus
#    dominios confiables. ¿Fue fácil decidir la lista? Esa dificultad es el costo del ground truth.
# 4. **Cambiar el prompt del componente.** Agregá a `buscar_referencias` la frase "Priorizá
#    fuentes académicas e institucionales" y volvé a correr la evaluación. ¿Mejora el ratio? Ahora
#    tenés una forma de saberlo sin leer los reportes.
# 5. **URLs con paréntesis.** La regex de `extraer_urls` corta en `)`, así que
#    `https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)` pierde el `)` final.
#    El dominio queda bien (la métrica no cambia) pero el link queda roto. ¿Cómo lo arreglarías
#    sin romper el caso `(ver https://arxiv.org/abs/1)`, donde el `)` NO es parte de la URL?
#    Pista: contar cuántos `(` y `)` tiene la URL candidata.

# %% [markdown]
# ## 6. Para cerrar
#
# - Evaluaste **un componente** del agente con una métrica objetiva calculada por código.
# - El ground truth es **por ejemplo**: cada tema tiene su propia lista de dominios confiables.
# - Corregiste tres defectos del material original: comparación por substring (falsos
#   positivos), URLs duplicadas que inflaban el total, y puntuación pegada a las URLs.
# - La misma idea escala: 10 o 20 temas, varias repeticiones, y un número que te dice si un
#   cambio en el prompt o en las tools mejoró la búsqueda, sin correr el pipeline completo.
#
# En el lab 02 vas a leer la app web que integra este agente y vas a ver dónde encajaría esta
# evaluación dentro de un sistema real.

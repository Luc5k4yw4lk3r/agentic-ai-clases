# %% [markdown]
# # Agente de investigación con function calling "a mano"
# **Módulo 3 · Lab 02.** Un agente que busca en arXiv y Wikipedia, escribe un informe
# con fuentes, lo critica, lo reescribe y lo publica como HTML. Esta vez sin `aisuite`:
# vas a escribir vos el loop que ayer hizo la librería.
#
# ## Objetivos
# Al terminar vas a poder:
# - Escribir el schema JSON de una tool a mano y explicar cada campo.
# - Leer un `tool_call` del SDK de OpenAI: `id`, `function.name`, `function.arguments`.
# - Implementar el loop de tool use: llamar, detectar `tool_calls`, ejecutar, devolver el
#   resultado como mensaje `tool`, repetir hasta la respuesta final.
# - Encadenar tools → reflexión → reescritura → formato en un pipeline de varias llamadas.
# - Estimar cuántas llamadas cuesta una corrida y por qué.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. Ayer, con `aisuite`, ¿qué activaba el loop de tool use?
#    a) `tools=[...]` solo.   b) El parámetro `max_turns`.   c) Un docstring que dijera "loop".
# 2. En el experimento de la tool que faltaba, ¿por qué el agente no pudo borrar el mail?
#    a) El modelo no sabía que existía el concepto de borrar.
#    b) `borrar_email` no estaba en la lista de tools; el modelo solo puede pedir lo que le ofrecés.
#    c) El servidor rechazó la llamada.
# 3. Con el SDK de OpenAI directo, cuando el modelo quiere usar una tool, ¿qué devuelve?
#    a) El resultado de la tool, ya ejecutada.
#    b) Un mensaje con `tool_calls`: nombre de la función y argumentos como string JSON, sin ejecutar nada.
#    c) Un error, porque el SDK no soporta tools.
# 4. ¿Qué tiene que tener el mensaje que le devolvés al modelo con el resultado de una tool?
#    a) `role: "user"` y el resultado como texto.
#    b) `role: "tool"`, el `tool_call_id` de la llamada que responde y el resultado en `content`.
#    c) `role: "assistant"` con el resultado.
# 5. `json.loads('{"query": "RAG", "max_results": 3}')` devuelve:
#    a) Un string.   b) Un dict de Python.   c) Una lista.

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (`max_turns`; sin él aisuite hace una sola llamada y devuelve
# los tool_calls sin ejecutar), 2-b (las tools disponibles definen las capacidades),
# 3-b (el SDK devuelve `message.tool_calls`; ejecutar es responsabilidad de tu código),
# 4-b (sin el `tool_call_id` correcto la API devuelve error 400), 5-b (dict; de ahí sale
# el `**args` para llamar a la función).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import json
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

from openai import OpenAI
from IPython.display import HTML, display

client = OpenAI()                  # SDK directo: el modelo va sin prefijo "openai:"

import research_tools              # arxiv_search_tool, wikipedia_search_tool, tavily_search_tool
import utils

print("Modelos:", MODEL_CHEAP, "|", MODEL_STRONG)
print("TAVILY_API_KEY:", "configurada" if utils.hay_tavily() else "no configurada (tavily cae a Wikipedia)")

# %% [markdown]
# ## 1. Lo que `aisuite` escondía
#
# **Para qué.** Ayer le pasaste funciones Python a `aisuite` y él hizo todo: armó los
# schemas, llamó al modelo, ejecutó las tools, devolvió los resultados, repitió. Hoy vas
# a ver cada una de esas piezas, porque cuando algo falla en producción (o cuando usás
# otro proveedor, u otro framework) lo que hay abajo es siempre esto.
#
# **Por qué así.** El protocolo de function calling de OpenAI tiene cuatro pasos:
#
# ```
# 1. Vos mandás messages + tools (una lista de schemas JSON).
# 2. El modelo responde con message.tool_calls: [ {id, function: {name, arguments}} ]
#    ("arguments" es un STRING con JSON adentro; nadie ejecutó nada todavía).
# 3. Vos ejecutás la función, y agregás a messages:
#      el mensaje del modelo (con sus tool_calls)
#      + un mensaje {"role": "tool", "tool_call_id": id, "content": resultado_como_string}
# 4. Volvés a llamar al modelo con los messages ampliados. Si responde con texto, terminaste;
#    si responde con más tool_calls, volvés al paso 3.
# ```
#
# `aisuite` hacía exactamente eso adentro de `max_turns`. Hoy el loop lo escribís vos.
#
# **Ejemplo práctico.** Las tools de hoy buscan información: `arxiv_search_tool`
# (papers), `wikipedia_search_tool` (definiciones) y `tavily_search_tool` (web general;
# si no hay `TAVILY_API_KEY` cae a Wikipedia y lo avisa). Están en `research_tools.py` y
# son funciones comunes. Probá una. Nota: **las queries van en inglés**, porque arXiv
# indexa casi todo en inglés y la Wikipedia en inglés es mucho más completa; el informe,
# en cambio, lo vamos a pedir en español.

# %%
papers = research_tools.arxiv_search_tool("retrieval augmented generation", max_results=3)
utils.mostrar_resultados(papers)

# %% [markdown]
# ## 2. El schema de una tool, escrito a mano
#
# Ayer `aisuite` generaba esto desde la firma y el docstring. Con el SDK directo lo
# escribís vos. Es un dict con una forma fija:
#
# ```python
# {
#   "type": "function",
#   "function": {
#     "name": "arxiv_search_tool",          # tiene que coincidir con la función que vas a ejecutar
#     "description": "...",                 # cuándo usarla (lo que ayer era la primera línea del docstring)
#     "parameters": {                       # un JSON Schema
#       "type": "object",
#       "properties": {
#         "query": {"type": "string", "description": "..."},
#         "max_results": {"type": "integer", "description": "...", "default": 5},
#       },
#       "required": ["query"],              # los que no tienen default
#     },
#   },
# }
# ```
#
# En `research_tools.py` ya está escrito el de arXiv. Miralo y compará con la firma de
# la función: cada parámetro de la firma es una clave en `properties`; los que no tienen
# default están en `required`.

# %%
arxiv_tool_def = research_tools.arxiv_tool_def
print(json.dumps(arxiv_tool_def, indent=2, ensure_ascii=False))

# %% [markdown]
# ### 2.1 Una llamada con tools, sin ejecutar nada (celda resuelta)
#
# Fijate qué devuelve el modelo cuando le pasás `tools=[arxiv_tool_def]` y un pedido
# que claramente necesita buscar. No va a haber resultados de arXiv: va a haber un
# **pedido de llamada**. Nadie ejecutó nada todavía.

# %%
mensajes_demo = [
    {"role": "system", "content": "Sos un asistente de investigación. Usá las tools cuando necesites información. Las queries a las tools van en inglés."},
    {"role": "user", "content": "Buscá en arXiv tres papers recientes sobre retrieval-augmented generation."},
]
respuesta_demo = client.chat.completions.create(model=MODEL_CHEAP, messages=mensajes_demo, tools=[arxiv_tool_def])

msg_demo = respuesta_demo.choices[0].message
print("content   :", repr(msg_demo.content))            # suele ser None: el modelo no "habló", pidió una tool
print("tool_calls:", len(msg_demo.tool_calls or []))
for call in msg_demo.tool_calls or []:
    print("  id       :", call.id)
    print("  name     :", call.function.name)
    print("  arguments:", repr(call.function.arguments), "<- es un string, hay que hacer json.loads")

# %% [markdown]
# ### 2.2 Una vuelta completa del loop, a mano (celda resuelta)
#
# Ahora ejecutamos lo que pidió y le devolvemos el resultado. Mirá la forma del mensaje
# `tool`: el `tool_call_id` tiene que ser el `id` del `call` que estamos respondiendo.
# Si no coincide, la API devuelve un error 400. Y antes del mensaje `tool` hay que agregar
# el mensaje del modelo (el que tenía los `tool_calls`), para que la conversación sea
# "pedí esto → acá está".

# %%
mensajes_demo.append(msg_demo)                           # 1) el mensaje del modelo, con sus tool_calls

for call in msg_demo.tool_calls:
    args = json.loads(call.function.arguments)           # 2) string JSON -> dict
    funcion = research_tools.tool_mapping[call.function.name]
    resultado = funcion(**args)                          # 3) ejecutar la función real
    mensajes_demo.append({                               # 4) devolver el resultado
        "role": "tool",
        "tool_call_id": call.id,
        "content": json.dumps(resultado, ensure_ascii=False),
    })
    print(f"Ejecuté {call.function.name}({args}) -> {len(resultado)} resultado(s)")

respuesta_final_demo = client.chat.completions.create(model=MODEL_CHEAP, messages=mensajes_demo, tools=[arxiv_tool_def])
print("\ntool_calls en la segunda respuesta:", respuesta_final_demo.choices[0].message.tool_calls)
print("\nRespuesta final:\n", respuesta_final_demo.choices[0].message.content)

# %% [markdown]
# ## 3. Tu primer schema: `wikipedia_tool_def`
#
# Escribí el schema de `wikipedia_search_tool` siguiendo el de arXiv. La firma de la
# función es:
#
# ```python
# def wikipedia_search_tool(query: str, max_results: int = 3, lang: str = "en") -> list[dict]
# ```
#
# Pensá qué va en `description` (¿para qué tipo de información conviene Wikipedia y no
# arXiv?), qué parámetros exponés y cuáles son `required`. Podés omitir `lang` si no
# querés que el modelo lo elija. En `research_tools.py` hay una versión de referencia:
# la celda de prueba compara la tuya con esa.

# %%
wikipedia_tool_def = {
    "type": "function",
    "function": {
        "name": "wikipedia_search_tool",
        ### BEGIN SOLUTION
        ### STUDENT: "description": "...",
        ### STUDENT: "parameters": {
        ### STUDENT:     "type": "object",
        ### STUDENT:     "properties": {
        ### STUDENT:         # "query": {...}, "max_results": {...}
        ### STUDENT:     },
        ### STUDENT:     "required": [],
        ### STUDENT: },
        "description": "Busca artículos en Wikipedia. Usar para definiciones, contexto general y conceptos establecidos; no para investigación de frontera.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tema a buscar, en inglés. Ej: 'retrieval-augmented generation'."},
                "max_results": {"type": "integer", "description": "Cantidad máxima de artículos (1 a 10).", "default": 3},
            },
            "required": ["query"],
        },
        ### END SOLUTION
    },
}

# %%
# Prueba rápida: misma forma que la referencia y usable como kwargs de la función real
utils.comparar_schemas(wikipedia_tool_def, research_tools.wikipedia_tool_def)
ejemplo_args = {"query": "retrieval-augmented generation", "max_results": 2}
print(json.dumps(research_tools.wikipedia_search_tool(**ejemplo_args), indent=2, ensure_ascii=False)[:600], "...")

# %% [markdown]
# ## 4. Despacho: de un nombre a una función
#
# El modelo devuelve el **nombre** de la tool como string. Para ejecutarla necesitás un
# diccionario nombre → función. Las claves tienen que coincidir exactamente con el
# `"name"` de cada schema.

# %%
TOOL_DEFS = [arxiv_tool_def, wikipedia_tool_def, research_tools.tavily_tool_def]

tool_mapping = {
    "arxiv_search_tool": research_tools.arxiv_search_tool,
    "wikipedia_search_tool": research_tools.wikipedia_search_tool,
    "tavily_search_tool": research_tools.tavily_search_tool,
}

for d in TOOL_DEFS:
    nombre = d["function"]["name"]
    assert nombre in tool_mapping, f"El schema {nombre} no tiene función en tool_mapping"
print("Schemas y mapping coinciden:", list(tool_mapping))

# %% [markdown]
# ## 5. El loop: `investigar_con_tools`
#
# Generalizá la vuelta a mano de la sección 2.2 en un `for` de hasta `max_turns` vueltas.
# Tres pasos por vuelta:
#
# 1. Llamar al modelo con `messages` y `tools=TOOL_DEFS`; agregar su mensaje a `messages`.
# 2. Si el mensaje **no** tiene `tool_calls`, es la respuesta final: devolver `content`.
# 3. Si tiene, ejecutar cada `call` (`json.loads` de los argumentos, buscar la función en
#    `tool_mapping`, llamarla con `**args`) y agregar el mensaje `{"role": "tool", ...}`.
#
# Si una tool falla (sin internet, API caída), no cortes el loop: devolvé al modelo
# `{"error": "..."}` como resultado, igual que ayer, para que decida qué hacer.
#
# El system prompt va en español y le pide al modelo que las queries vayan en inglés.
# Imprimí cada llamada a tool para ver la traza mientras corre.

# %%
SYSTEM_INVESTIGADOR = """Sos un asistente de investigación. Escribís informes breves, precisos y con fuentes.

- Usá las tools para buscar información antes de escribir: arXiv para papers, Wikipedia para definiciones y contexto, búsqueda web para lo reciente.
- Las queries a las tools van en INGLÉS (los índices están en inglés). El informe va en ESPAÑOL.
- Citá cada afirmación con la URL de la fuente. No inventes fuentes ni dejes marcadores tipo "(cita pendiente)".
- Organizá el informe en secciones con títulos. Tono técnico, sin relleno.
- Cuando tengas suficiente información, escribí el informe final sin pedir más tools.
"""


def investigar_con_tools(pedido: str, model: str = MODEL_CHEAP, max_turns: int = 8) -> str:
    """Investiga un tema llamando a las tools en loop y devuelve el informe final (texto).

    Cada vuelta del loop es una llamada al modelo. Si pide tools, se ejecutan y los
    resultados vuelven como mensajes de rol "tool"; si responde con texto, ese texto es
    el informe y se devuelve. Si se agotan los turnos sin respuesta final, levanta
    RuntimeError con un mensaje legible.

    Args:
        pedido: qué investigar, en español.
        model: nombre del modelo (sin prefijo de proveedor).
        max_turns: cantidad máxima de llamadas al modelo.

    Returns:
        El informe final como texto (markdown o texto plano, según decida el modelo).
    """
    messages = [
        {"role": "system", "content": SYSTEM_INVESTIGADOR},
        {"role": "user", "content": pedido},
    ]
    for turno in range(1, max_turns + 1):
        # Paso 1: llamar al modelo con las tools y agregar su mensaje a messages
        ### BEGIN SOLUTION
        ### STUDENT: msg = None  # Pista: client.chat.completions.create(model=..., messages=..., tools=TOOL_DEFS) -> .choices[0].message
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOL_DEFS)
        msg = response.choices[0].message
        messages.append(msg)
        ### END SOLUTION
        # Paso 2: si no pidió tools, es la respuesta final
        ### BEGIN SOLUTION
        if not msg.tool_calls:
            print(f"[turno {turno}] respuesta final ({len(msg.content or '')} caracteres)")
            return msg.content
        ### END SOLUTION
        # Paso 3: ejecutar cada tool_call y devolver el resultado como mensaje "tool"
        ### BEGIN SOLUTION
        for call in msg.tool_calls:
            nombre = call.function.name
            args = json.loads(call.function.arguments)
            print(f"[turno {turno}] {nombre}({args})")
            try:
                resultado = tool_mapping[nombre](**args)
            except Exception as e:  # sin internet, API caída, argumento inválido: el modelo decide
                resultado = {"error": f"{type(e).__name__}: {e}"}
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(resultado, ensure_ascii=False),
            })
        ### END SOLUTION
    raise RuntimeError(
        f"El agente agotó los {max_turns} turnos sin dar una respuesta final. "
        "Subí max_turns o acotá el pedido."
    )

# %%
# Prueba rápida SIN API: un cliente falso que simula "pide arXiv -> responde".
# Verifica que el loop arme bien los mensajes "tool" (tool_call_id correcto) y respete max_turns.
from tests import run_all

run_all(investigar_con_tools)

# %%
# Ahora con el modelo real. Mirá la traza: cuántos turnos, qué tools, qué queries eligió.
PEDIDO = (
    "Escribí un informe breve (300 a 500 palabras) sobre retrieval-augmented generation (RAG): "
    "qué es, cuándo conviene usarlo en vez de fine-tuning, y sus limitaciones conocidas. "
    "Consultá al menos un paper de arXiv y una definición de Wikipedia."
)
informe = investigar_con_tools(PEDIDO)
print("\n" + informe)

# %% [markdown]
# ## 6. Reflexión en dos llamadas: `reflexionar_y_reescribir`
#
# El patrón de M2, aplicado al informe. **Dos llamadas separadas**: una que critica y otra
# que reescribe *a partir de la crítica*. (El lab original hacía una sola llamada y
# devolvía el mismo texto como "crítica" y como "informe revisado"; eso no es reflexión,
# es un rename.)
#
# Devolvé un dict con dos claves: `critica` e `informe_revisado`. Usá `MODEL_STRONG`:
# criticar bien es más difícil que generar.

# %%
PROMPT_CRITICA = """Sos un revisor académico exigente. Leé el informe y escribí una crítica estructurada en español con cuatro secciones: Fortalezas, Limitaciones, Sugerencias concretas, Fuentes (¿están citadas? ¿alguna parece inventada o irrelevante?). Sé específico: citá frases del informe.

Informe:
{informe}
"""

PROMPT_REESCRITURA = """Sos un editor técnico. Reescribí el informe incorporando la crítica: corregí lo señalado, mantené las fuentes válidas con sus URLs, no agregues fuentes nuevas que no estén en el informe original. Devolvé solo el informe revisado, en español, con la misma estructura de secciones.

Informe original:
{informe}

Crítica del revisor:
{critica}
"""


def reflexionar_y_reescribir(informe: str, model: str = MODEL_STRONG) -> dict:
    """Critica un informe y lo reescribe a partir de la crítica, en dos llamadas separadas.

    Args:
        informe: el texto que devolvió investigar_con_tools.
        model: modelo para ambas llamadas (default MODEL_STRONG).

    Returns:
        Dict con las claves "critica" (texto) e "informe_revisado" (texto).
    """
    if not informe or not informe.strip():
        raise ValueError("El informe está vacío: no hay nada que criticar")
    # Paso 1: pedir la crítica (PROMPT_CRITICA con el informe adentro)
    ### BEGIN SOLUTION
    r1 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT_CRITICA.format(informe=informe)}],
    )
    critica = r1.choices[0].message.content
    if not critica or not critica.strip():
        raise ValueError("El modelo devolvió una crítica vacía")
    ### END SOLUTION
    # Paso 2: pedir la reescritura (PROMPT_REESCRITURA con informe y crítica) y devolver el dict
    ### BEGIN SOLUTION
    r2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT_REESCRITURA.format(informe=informe, critica=critica)}],
    )
    revisado = r2.choices[0].message.content
    if not revisado or not revisado.strip():
        raise ValueError("El modelo devolvió un informe revisado vacío")
    return {"critica": critica, "informe_revisado": revisado}
    ### END SOLUTION

# %%
# Prueba rápida sin API: dos llamadas, la segunda recibe la crítica de la primera
run_all(reflexionar_y_reescribir)

# %%
# Con el modelo real, sobre el informe de la sección 5
resultado = reflexionar_y_reescribir(informe)
print("=== CRÍTICA ===\n", resultado["critica"])
print("\n=== INFORME REVISADO ===\n", resultado["informe_revisado"])

# %% [markdown]
# ## 7. Publicar: `convertir_a_html`
#
# Última llamada del pipeline: el informe revisado a HTML para compartirlo. Dos cosas a
# cuidar que el original no cuidaba:
#
# - Los modelos suelen envolver el código en fences de markdown (```` ```html ... ``` ````).
#   Si los dejás, el navegador los muestra como texto. Hay que quitarlos.
# - Validá que lo que volvió parece HTML (tiene `<`); si no, `ValueError` con un mensaje
#   claro en vez de mostrar una página vacía.
#
# Formatear es trabajo barato: `MODEL_CHEAP` alcanza.

# %%
PROMPT_HTML = """Convertí este informe a un documento HTML completo y limpio: <h1> para el título, <h2> para las secciones, párrafos, listas si corresponde, y todas las URLs como enlaces <a href> clickeables. Incluí un <style> mínimo para que sea legible (ancho máximo, tipografía, espaciado). Respondé SOLO con el HTML, sin explicaciones ni fences de markdown.

Informe:
{informe}
"""


def quitar_fences(texto: str) -> str:
    """Quita los fences de markdown (```html ... ```) si el modelo los agregó igual."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        primera_linea_fin = limpio.find("\n")
        limpio = limpio[primera_linea_fin + 1:] if primera_linea_fin != -1 else ""
    if limpio.endswith("```"):
        limpio = limpio[: -3]
    return limpio.strip()


def convertir_a_html(informe: str, model: str = MODEL_CHEAP) -> str:
    """Convierte un informe en texto a un documento HTML, sin fences de markdown.

    Args:
        informe: texto del informe (idealmente el revisado).
        model: modelo a usar (default MODEL_CHEAP; es solo formato).

    Returns:
        El HTML como string, listo para display(HTML(...)) o para guardar en un archivo.
    """
    if not informe or not informe.strip():
        raise ValueError("El informe está vacío: no hay nada que convertir")
    # Paso 1: pedir el HTML al modelo (PROMPT_HTML)
    ### BEGIN SOLUTION
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT_HTML.format(informe=informe)}],
    )
    crudo = r.choices[0].message.content or ""
    ### END SOLUTION
    # Paso 2: quitar fences, validar que parece HTML y devolver
    ### BEGIN SOLUTION
    html = quitar_fences(crudo)
    if "<" not in html or ">" not in html:
        raise ValueError(f"El modelo no devolvió HTML. Empieza así: {html[:120]!r}")
    return html
    ### END SOLUTION

# %%
# Prueba rápida sin API: fences quitados, validación de HTML
run_all(convertir_a_html)

# %%
# Con el modelo real
html = convertir_a_html(resultado["informe_revisado"])
print(html[:400], "\n...")
display(HTML(html))

# %% [markdown]
# ## 8. Pipeline completo y costo
#
# Las tres funciones encadenadas. Antes de correrlo, estimá: `investigar_con_tools` usa
# entre 2 y 6 llamadas (una por turno), `reflexionar_y_reescribir` 2, `convertir_a_html` 1.
# **Una corrida completa son entre 5 y 10 llamadas**, y la mitad van a `MODEL_STRONG` con
# un informe entero adentro. No lo corras en loop "para ver qué pasa".
#
# `utils.pipeline_completo` recibe tus tres funciones, las encadena, cuenta las llamadas y
# guarda el HTML en `informes/<slug>.html` para que lo abras en el navegador.

# %%
TEMA = "Agentes de IA que usan tools (function calling): estado del arte, riesgos y buenas prácticas"
salida = utils.pipeline_completo(
    TEMA,
    investigar=investigar_con_tools,
    reflexionar=reflexionar_y_reescribir,
    a_html=convertir_a_html,
    client=client,
)
print("Llamadas al modelo:", salida["llamadas"])
print("Archivo:", salida["archivo"])
display(HTML(salida["html"]))

# %% [markdown]
# ## 9. Si te sobra tiempo
#
# Consignas abiertas, sin solución en el notebook (hay pistas en el workbook):
#
# 1. **Sin Wikipedia.** Sacá `wikipedia_tool_def` de `TOOL_DEFS` y repetí el pedido de la
#    sección 5. ¿Cómo consigue el modelo las definiciones? ¿Cambia la cantidad de turnos?
# 2. **Traza completa.** Hacé que `investigar_con_tools` devuelva también la lista
#    `messages` (por ejemplo, un dict con `informe` y `messages`) y escribí una
#    `mostrar_traza(messages)` como la de ayer, pero para esta forma de mensajes.
# 3. **Crítica con criterios.** Cambiá `PROMPT_CRITICA` para que evalúe con tres criterios
#    de 1 a 5 (fuentes, precisión, claridad) y devuelva JSON. Parseá con `json.loads` y
#    validá las claves. Decidí: si el puntaje de fuentes es menor a 3, ¿volvés a investigar?
# 4. **Tool nueva.** Escribí una tool `fecha_de_hoy() -> str` (sin parámetros) con su schema
#    y agregala. Pedí un informe sobre "lo publicado este mes". ¿La usa? ¿La usa cuando no
#    hace falta?

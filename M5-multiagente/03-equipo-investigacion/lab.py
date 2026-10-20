# %% [markdown]
# # Equipo de investigación: planner, executor y tres especialistas
# **Módulo 5 · Lab 03.** Un planner arma la lista de pasos; un executor rutea cada paso a
# un agente especialista (Research con tools, Writer, Editor) y acumula lo que cada uno
# produjo, hasta terminar con un informe en Markdown.
#
# ## Objetivos
# Al terminar vas a poder:
# - Diseñar un equipo de agentes con roles distintos y explicar por qué un executor que
#   **rutea** es distinto de un agente que hace todo.
# - Hacer que un planner devuelva una lista de pasos en JSON y parsearla con validación
#   (nada de `eval()`).
# - Darle tools a un agente con `aisuite` (funciones Python + `max_turns`) y nombrarlas en
#   el system prompt con sus nombres reales.
# - Mantener un historial `(paso, agente, salida)` y pasárselo al siguiente agente como
#   contexto.
# - Estimar el costo en llamadas de una corrida y decidir cuándo conviene acortar el plan.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. (Repaso sesión 1) En el lab 02 el modelo escribía código y lo ejecutábamos con `exec`.
#    ¿Qué controla el namespace que le pasamos a `exec`? a) Qué puede hacer el código
#    b) Qué variables ve el código  c) Cuánto tiempo puede correr
# 2. (Repaso sesión 1) ¿Cuál era la ventaja del plan como JSON de tools (lab 01) frente al
#    código como plan (lab 02)? a) Más expresivo  b) Catálogo cerrado: el peor caso es
#    `Tool desconocida`  c) Más rápido
# 3. (Nuevo) En este lab el executor le pregunta a un LLM "¿qué agente hace este paso?" y
#    recibe `{"agente": "agente_research", "tarea": "..."}`. ¿Qué hace con eso?
#    a) Lo imprime  b) Busca la función en `registro_agentes` y la llama con la tarea más
#    el historial  c) Se lo pasa al planner para que lo apruebe
# 4. (Nuevo) El agente Research recibe las tools como **funciones Python** y `max_turns=6`.
#    ¿Quién ejecuta las funciones cuando el modelo las pide? a) OpenAI  b) `aisuite`, en
#    tu máquina, hasta 6 vueltas  c) Nadie: el modelo solo describe qué haría
# 5. (Base, Python) `historial = [("buscar", "agente_research", "texto")]`. ¿Qué devuelve
#    `historial[-1][1]`? a) `"buscar"`  b) `"agente_research"`  c) `"texto"`

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (controla qué variables ve, no qué puede hacer: por eso
# `__builtins__` era el agujero), 2-b (el catálogo cerrado acota el daño; el código como
# plan es más expresivo pero depende del prompt), 3-b (el executor es un *router*: despacha
# por nombre y agrega el historial a la tarea), 4-b (aisuite corre el loop de tool calling
# localmente y llama a tus funciones; `max_turns` es el tope de vueltas), 5-b (tupla
# `(paso, agente, salida)`: índice 1 es el agente).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

import json
from datetime import date

import aisuite as ai

import research_tools   # arxiv_search_tool, tavily_search_tool, wikipedia_search_tool (dado)
import utils            # limpiar_json, print_html, mostrar_markdown, guardar_informe (dado)

client = ai.Client()
AI_CHEAP = f"openai:{MODEL_CHEAP}"
AI_STRONG = f"openai:{MODEL_STRONG}"

if not os.getenv("TAVILY_API_KEY", "").strip() or os.getenv("TAVILY_API_KEY", "").startswith("tvly-..."):
    print("AVISO: sin TAVILY_API_KEY. tavily_search_tool va a usar Wikipedia como fallback (el lab funciona igual).")

# %% [markdown]
# ## 1. Un equipo, no un agente
#
# **Para qué.** En M3 un solo agente buscaba, escribía y corregía. Funciona, pero el prompt
# se vuelve enorme y nadie sabe qué parte falló. Acá dividimos el trabajo en **roles**
# chicos, cada uno con su prompt y su modelo:
#
# | Agente | Modelo | Tiene tools | Qué hace |
# |---|---|---|---|
# | `agente_planner` | fuerte | no | convierte el tema en una lista de pasos |
# | `agente_research` | barato | **sí** (arXiv, Tavily, Wikipedia) | busca y resume fuentes |
# | `agente_writer` | barato | no | redacta secciones o el informe |
# | `agente_editor` | fuerte | no | critica y mejora borradores |
# | `agente_executor` | barato (para rutear) | no | recorre el plan, elige quién hace cada paso, acumula historial |
#
# **Por qué así.** El executor es el pegamento: no investiga ni escribe. Para cada paso le
# pregunta a un modelo barato "¿quién hace esto y cuál es la tarea limpia?", recibe un JSON
# chico, busca la función en un diccionario (`registro_agentes`) y la llama. Lo que esa
# función devuelve se guarda en un **historial** que viaja con el siguiente paso.
#
# ```text
# tema ──► agente_planner ──► ["paso 1", "paso 2", ..., "paso N: escribir el informe en Markdown"]
#                                   │
#                                   ▼
#                            agente_executor
#                            para cada paso:
#                              LLM barato ──► {"agente": "...", "tarea": "..."}
#                              registro_agentes[agente](tarea + historial) ──► salida
#                              historial.append((paso, agente, salida))
#                                   │
#                                   ▼
#                         historial[-1][2]  = el informe en Markdown  ──► data/informe.md
# ```
#
# **Costo.** Una corrida completa son entre 15 y 25 llamadas (1 del planner, 1 de ruteo por
# paso, 1 por agente por paso y hasta 6 vueltas de tools en cada Research). Por eso en clase
# corremos el pipeline entero **una sola vez** y para practicar usamos planes cortos de 3
# pasos (sección 7).

# %% [markdown]
# ## 2. Las tools del agente Research
#
# Son las mismas tres de M3 y M4 (`research_tools.py`). Con `aisuite` no hace falta escribir
# el schema JSON a mano: le pasás la **función** y arma el schema desde el docstring. Por
# eso los docstrings están en español y son precisos.
#
# **Nota sobre el idioma.** Los prompts de este lab están en español, pero las *queries* a
# arXiv y Tavily van en inglés: arXiv indexa en inglés y Tavily devuelve mejores resultados.
# El system prompt del Research se lo pide explícitamente.

# %%
# Probamos una tool a mano. Wikipedia no necesita key.
resultados = research_tools.wikipedia_search_tool("ensemble Kalman filter", max_results=2)
for r in resultados:
    print(f"- {r['title']}: {r['snippet'][:120]}...  ({r['url']})")

# Y vemos el schema que aisuite genera a partir del docstring (esto es lo que ve el modelo)
from aisuite.utils.tools import Tools
schema = Tools([research_tools.arxiv_search_tool]).tools()[0]
utils.print_html(schema, title="Schema que aisuite arma para arxiv_search_tool")

# %% [markdown]
# ## 3. Ejemplo resuelto: un agente sin tools con aisuite
#
# Todos los agentes de este lab siguen la misma forma. Mirá `agente_resumidor`: system prompt
# con el rol, user con la tarea, `client.chat.completions.create(model=..., messages=...)`,
# y el texto sale de `response.choices[0].message.content`. Los huecos del lab son
# variaciones de esto.

# %%
def agente_resumidor(texto: str, model: str = AI_CHEAP) -> str:
    """Ejemplo resuelto: resume un texto en una oración."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Sos un asistente que resume textos técnicos en UNA oración clara, en español."},
            {"role": "user", "content": texto},
        ],
    )
    return response.choices[0].message.content


print(agente_resumidor(resultados[0]["snippet"]))

# %% [markdown]
# ## 4. Planner: del tema a la lista de pasos
#
# **Para qué.** Convertir "el filtro de Kalman por conjuntos para pronóstico" en 4 a 6 pasos
# atómicos que los tres especialistas puedan ejecutar.
#
# **Por qué así.** Pedimos una **lista JSON de strings**. El original pedía "una lista de
# Python" y la leía con `eval()`: eso ejecuta cualquier cosa que el modelo escriba. Acá
# `utils.limpiar_json` saca las fences de markdown y `json.loads` la convierte; después
# validamos que sea una lista de textos no vacía. Si no, `ValueError` legible.
#
# El último paso tiene que ser **escribir el informe completo en Markdown**: es lo que vamos
# a guardar en `data/informe.md`.

# %%
def agente_planner(tema: str, model: str = AI_STRONG) -> list[str]:
    """Planner: devuelve la lista de pasos (strings) para investigar y redactar un informe sobre `tema`.

    Returns:
        lista de 4 a 6 pasos atómicos; el último produce el informe completo en Markdown.
    """
    prompt = f"""Sos el agente planificador de un equipo de investigación con tres especialistas:
- agente_research: busca información en arXiv, Wikipedia y la web (tiene tools de búsqueda).
- agente_writer: redacta secciones, resúmenes y el informe final.
- agente_editor: critica y mejora borradores.

Escribí un plan de entre 4 y 6 pasos para producir un informe breve sobre el tema de abajo.
Reglas:
- Cada paso es UNA tarea atómica que puede hacer uno solo de los tres agentes.
- Nada de tareas ajenas (crear archivos, instalar paquetes, armar repositorios).
- Los pasos de búsqueda indican qué buscar; los de redacción, qué sección escribir; los de edición, qué revisar.
- El ÚLTIMO paso es siempre: redactar el informe completo en formato Markdown, incorporando las correcciones.
- Respondé ÚNICAMENTE con una lista JSON de strings, sin texto antes ni después. Ejemplo:
  ["Buscar en arXiv ...", "Buscar en Wikipedia ...", "Redactar ...", "Revisar ...", "Redactar el informe completo en Markdown ..."]

Tema: "{tema}"
"""
    # Paso 1: llamar al modelo con el prompt como único mensaje de rol "user" y guardar el texto en `contenido`.
    ### BEGIN SOLUTION
    response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    contenido = response.choices[0].message.content
    ### END SOLUTION

    # Paso 2: convertir con json.loads(utils.limpiar_json(contenido)); validar que sea una lista
    # no vacía donde cada elemento es un str no vacío (si no, ValueError en español). Devolver la lista.
    ### BEGIN SOLUTION
    pasos = json.loads(utils.limpiar_json(contenido))
    if not isinstance(pasos, list) or len(pasos) == 0:
        raise ValueError(f"El planner tenía que devolver una lista JSON no vacía y devolvió: {contenido[:200]!r}")
    for i, paso in enumerate(pasos, start=1):
        if not isinstance(paso, str) or not paso.strip():
            raise ValueError(f"El paso {i} del plan no es un texto: {paso!r}")
    return [paso.strip() for paso in pasos]
    ### END SOLUTION

# %%
# Prueba rápida (1 llamada al modelo fuerte)
TEMA = "El filtro de Kalman por conjuntos (ensemble Kalman filter) para pronóstico de series de tiempo"
pasos = agente_planner(TEMA)
for i, paso in enumerate(pasos, start=1):
    print(f"{i}. {paso}")

# %% [markdown]
# ## 5. Los tres especialistas
#
# ### 5.1 Research: el único con tools
#
# **Para qué.** Buscar fuentes y devolver un resumen con títulos, URLs y hallazgos.
#
# **Por qué así.** Con `aisuite`, `tools=[funciones]` + `max_turns=6` hace el loop completo:
# el modelo pide una tool, aisuite la ejecuta, le devuelve el resultado, y así hasta que el
# modelo responde en texto o se agotan las vueltas. Bajamos `max_turns` de 12 (original) a 6
# por costo: para un paso de búsqueda alcanzan 2 o 3 llamadas a tools.
#
# El system prompt nombra las tools **con sus nombres reales** (`arxiv_search_tool`,
# `tavily_search_tool`, `wikipedia_search_tool`). El original decía `arxiv_tool`,
# `tavily_tool`, `wikipedia_tool`, que no existían: el modelo tenía que adivinar la
# correspondencia leyendo los schemas.

# %%
def agente_research(tarea: str, model: str = AI_CHEAP, max_turns: int = 6) -> str:
    """Research: ejecuta una tarea de búsqueda usando las tres tools y devuelve un resumen con fuentes.

    Returns:
        texto en español con los hallazgos, citando título y URL de cada fuente usada.
    """
    system = f"""Sos el agente de investigación de un equipo. Hoy es {date.today().isoformat()}.
Tenés tres tools:
- arxiv_search_tool(query, max_results): papers académicos. Para fundamentos técnicos.
- wikipedia_search_tool(query, max_results): definiciones y contexto general.
- tavily_search_tool(query, max_results): web general (noticias, blogs, docs). Para lo reciente.
Escribí las queries en INGLÉS (los índices están en inglés). Usá 2 o 3 búsquedas, no más.
Cuando tengas suficiente, respondé en ESPAÑOL con un resumen de los hallazgos y una lista de
fuentes con título y URL. No inventes fuentes: solo las que devolvieron las tools."""
    # Paso 1: llamar al modelo con system + user (la tarea), pasando
    # tools=[research_tools.arxiv_search_tool, research_tools.tavily_search_tool, research_tools.wikipedia_search_tool]
    # y max_turns=max_turns. Guardar la respuesta en `response`.
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": tarea}],
        tools=[research_tools.arxiv_search_tool, research_tools.tavily_search_tool, research_tools.wikipedia_search_tool],
        max_turns=max_turns,
    )
    ### END SOLUTION

    # Paso 2: contar cuántos mensajes de rol "tool" hay en response.choices[0].intermediate_messages
    # (si el atributo existe) e imprimir "  tools usadas: N". Devolver el contenido del mensaje final;
    # si es None (se agotaron los turnos), devolver un texto que lo diga.
    ### BEGIN SOLUTION
    intermedios = getattr(response.choices[0], "intermediate_messages", []) or []
    usadas = 0
    for m in intermedios:
        rol = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        if rol == "tool":
            usadas += 1
    print(f"  tools usadas: {usadas}")
    contenido = response.choices[0].message.content
    if not contenido:
        return f"[agente_research agotó {max_turns} turnos sin redactar un resumen; revisá la tarea o subí max_turns]"
    return contenido
    ### END SOLUTION

# %%
# Prueba rápida (1 llamada + hasta 6 vueltas de tools)
print(agente_research("Buscar en Wikipedia y arXiv qué es el ensemble Kalman filter y en qué se diferencia del filtro de Kalman clásico. Resumir en 5 líneas con fuentes.")[:1500])

# %% [markdown]
# ### 5.2 Writer y Editor: sin tools, distinto modelo
#
# Son dos variaciones de `agente_resumidor`. El Writer usa el modelo barato (redactar es
# generación); el Editor usa el fuerte (criticar bien es más difícil, como el reflector del
# lab 01).

# %%
def agente_writer(tarea: str, model: str = AI_CHEAP) -> str:
    """Writer: redacta secciones, resúmenes o el informe completo a partir de la tarea y el contexto que trae."""
    # Único paso: system "redactor técnico que escribe en español, claro y estructurado, en Markdown
    # cuando se lo piden; usa solo la información del contexto, sin inventar datos ni fuentes" + user (tarea).
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "Sos el agente redactor de un equipo de investigación. Escribís en español, claro y bien "
                "estructurado, en Markdown cuando te lo piden. Usás solo la información que hay en el contexto "
                "de la tarea; no inventás datos, cifras ni fuentes. Si falta información, lo decís."
            )},
            {"role": "user", "content": tarea},
        ],
    )
    return response.choices[0].message.content
    ### END SOLUTION


def agente_editor(tarea: str, model: str = AI_STRONG) -> str:
    """Editor: critica un borrador (claridad, estructura, afirmaciones sin fuente) y propone mejoras concretas."""
    # Único paso: system "editor que revisa borradores: señala problemas de claridad, estructura y
    # afirmaciones sin respaldo, y devuelve una lista de correcciones concretas o el texto mejorado" + user (tarea).
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "Sos el agente editor de un equipo de investigación. Revisás borradores en español: señalás "
                "problemas de claridad, estructura, repeticiones y afirmaciones sin fuente, y devolvés una lista "
                "de correcciones concretas (o el texto mejorado si la tarea lo pide). Sos directo y breve."
            )},
            {"role": "user", "content": tarea},
        ],
    )
    return response.choices[0].message.content
    ### END SOLUTION

# %%
# Prueba rápida (2 llamadas)
borrador = agente_writer("Escribí un párrafo de 4 líneas que explique qué es un filtro de Kalman a alguien que sabe programar pero no sabe estadística.")
print(borrador)
print("\n--- EDITOR ---")
print(agente_editor(f"Revisá este párrafo y listá 3 mejoras concretas:\n\n{borrador}"))

# %% [markdown]
# ## 6. Executor: el router con memoria
#
# **Para qué.** Recorrer el plan y, para cada paso, decidir **quién** lo hace y **con qué
# contexto**.
#
# **Por qué así.** La decisión de ruteo la toma un modelo barato con un prompt muy acotado:
# devuelve `{"agente": ..., "tarea": ...}`. El executor valida el JSON (otra vez
# `limpiar_json`), verifica que el agente exista en `registro_agentes`, arma la tarea
# "enriquecida" con el historial de pasos anteriores, y llama a la función. Todo lo que pasa
# se registra como `(paso, agente, salida)`.
#
# El historial es lo que hace que el equipo sea un equipo: el Writer del paso 4 ve lo que
# el Research encontró en los pasos 1 y 2.

# %%
registro_agentes = {
    "agente_research": agente_research,
    "agente_writer": agente_writer,
    "agente_editor": agente_editor,
}


def armar_contexto(historial: list[tuple[str, str, str]]) -> str:
    """Convierte el historial en texto para pegarlo en la tarea del siguiente agente."""
    if not historial:
        return "(todavía no se ejecutó ningún paso)"
    bloques = []
    for i, (paso, agente, salida) in enumerate(historial, start=1):
        bloques.append(f"### Paso {i} — hecho por {agente}\nTarea: {paso}\nResultado:\n{salida}")
    return "\n\n".join(bloques)


def agente_executor(pasos: list[str], model: str = AI_CHEAP) -> list[tuple[str, str, str]]:
    """Executor: rutea cada paso al agente correcto y acumula el historial.

    Args:
        pasos: lista de pasos del planner.
        model: modelo barato para decidir el ruteo (los agentes usan su propio default).

    Returns:
        lista de tuplas (paso, nombre_del_agente, salida), una por paso, en orden.
    """
    historial: list[tuple[str, str, str]] = []
    nombres = list(registro_agentes.keys())
    for i, paso in enumerate(pasos, start=1):
        prompt_ruteo = f"""Sos el coordinador de un equipo de investigación. Decidí qué agente ejecuta esta instrucción
y reescribila como una tarea limpia y concreta para ese agente.

Agentes disponibles: {nombres}
- agente_research: buscar información (tiene tools de búsqueda).
- agente_writer: redactar, resumir, escribir el informe.
- agente_editor: revisar, criticar, corregir borradores.

Respondé ÚNICAMENTE con un JSON con dos claves: "agente" (uno de la lista) y "tarea" (string). Sin explicaciones.

Instrucción: "{paso}"
"""
        # Paso 1: llamar al modelo con prompt_ruteo (rol user), parsear con json.loads(utils.limpiar_json(...))
        # y validar que `agente` esté en registro_agentes y que `tarea` sea un str no vacío (si no, ValueError).
        ### BEGIN SOLUTION
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt_ruteo}])
        decision = json.loads(utils.limpiar_json(response.choices[0].message.content))
        agente = decision.get("agente")
        tarea = decision.get("tarea")
        if agente not in registro_agentes:
            raise ValueError(f"El router eligió un agente desconocido: {agente!r}. Los válidos son {nombres}.")
        if not isinstance(tarea, str) or not tarea.strip():
            raise ValueError(f"El router devolvió una tarea vacía para el paso {i}: {decision!r}")
        ### END SOLUTION

        # Paso 2: armar la tarea enriquecida ("Sos {agente}. Contexto de lo hecho hasta ahora:\n{armar_contexto(historial)}\n\nTu tarea ahora:\n{tarea}"),
        # imprimir un log legible, llamar a registro_agentes[agente](tarea_enriquecida) y agregar (paso, agente, salida) al historial.
        ### BEGIN SOLUTION
        tarea_enriquecida = (
            f"Sos {agente}, parte de un equipo de investigación.\n\n"
            f"## Contexto de lo hecho hasta ahora\n{armar_contexto(historial)}\n\n"
            f"## Tu tarea ahora\n{tarea}"
        )
        print(f"\n[{i}/{len(pasos)}] {agente}  ←  {tarea[:110]}{'...' if len(tarea) > 110 else ''}")
        salida = registro_agentes[agente](tarea_enriquecida)
        print(f"      → {len(salida)} caracteres")
        historial.append((paso, agente, salida))
        ### END SOLUTION
    return historial

# %%
# Prueba rápida con un plan CORTO escrito a mano (3 pasos → 3 ruteos + 3 agentes + tools ≈ 8 a 10 llamadas).
# Trabajá sobre este plan mientras desarrollás; el plan completo del planner se corre una sola vez al final.
PLAN_CORTO = [
    "Buscar en Wikipedia y arXiv una definición del ensemble Kalman filter y dos aplicaciones, con fuentes.",
    "Redactar un resumen de 2 párrafos en español con lo encontrado, citando las fuentes.",
    "Redactar el informe completo en formato Markdown con título, resumen, aplicaciones y fuentes.",
]
historial_corto = agente_executor(PLAN_CORTO)
print("\n" + utils.resumen_historial(historial_corto))
assert len(historial_corto) == 3 and all(len(t) == 3 for t in historial_corto)

# %% [markdown]
# ## 7. Corrida completa y guardado del informe
#
# Esta celda corre el equipo entero con el plan del planner (sección 4). Son entre 15 y 25
# llamadas: **correrla una vez**. El informe queda en `historial[-1][2]` y se guarda en
# `data/informe.md`.

# %%
historial = agente_executor(pasos)

informe = utils.quitar_fences(historial[-1][2])   # por si el Writer envolvió el Markdown en ```markdown
ruta = utils.guardar_informe(informe, "data/informe.md")
print(f"\nInforme guardado en {ruta} ({len(informe)} caracteres)")
utils.mostrar_markdown(informe)

# %% [markdown]
# ## 8. Para llevarse
#
# - **Roles chicos, prompts chicos.** Cada agente hace una cosa y se puede probar solo.
# - **El executor rutea, no piensa.** Un modelo barato decide "quién"; la función elegida
#   hace el trabajo; el historial conecta los pasos.
# - **Validar siempre lo que devuelve un LLM.** `limpiar_json` + `json.loads` + chequeo de
#   tipo. Nunca `eval()`.
# - **Nombrar las tools como se llaman.** Si el system prompt dice `arxiv_tool` y la tool
#   es `arxiv_search_tool`, el modelo tiene que adivinar.
# - **El costo se diseña.** `max_turns`, cantidad de pasos y qué modelo usa cada rol son
#   decisiones, no accidentes.
#
# ## Si te sobra tiempo
#
# Consignas abiertas (no están resueltas en este notebook; ver el workbook):
#
# 1. Contá las llamadas reales de una corrida: envolvé `client.chat.completions.create` en
#    una función que incremente un contador. ¿Cuántas fueron? ¿Cuántas de Research?
# 2. Agregá un cuarto agente, `agente_verificador`, que reciba el informe final y chequee
#    que cada URL citada aparece en alguna salida de Research del historial. Sumalo a
#    `registro_agentes` y al prompt del planner.
# 3. Reemplazá el ruteo por LLM con un ruteo por palabras clave ("buscar" → research,
#    "revisar" → editor, resto → writer). ¿En qué pasos se equivoca? ¿Vale la llamada extra?
# 4. Hacé que el executor pase al siguiente agente solo las **últimas dos** salidas del
#    historial en vez de todo. ¿Cambia la calidad del informe? ¿Cuánto bajan los tokens?

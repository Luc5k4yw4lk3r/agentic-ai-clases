# Ejercicios — La app del agente de investigación

Trabajás sobre `app/`. Antes de tocar nada, hacé una corrida completa con un prompt corto y
guardá el `task_id`: vas a comparar contra eso. Las soluciones no están acá; están en la guía
docente para que las pida el profesor cuando corresponda.

Reglas del juego:

- Corré la app con `uvicorn main:app --reload` (sqlite): cada cambio se recarga solo.
- Cada corrida completa cuesta entre 8 y 12 llamadas al modelo. Para probar un cambio chico
  no hace falta la corrida entera: casi todo se puede probar llamando a la función desde un
  `python -c` o un notebook con agentes falsos (ver el truco al final).

## Parte A. Caza de bugs (30 min)

Para cada caso tenés el **síntoma** que ve el usuario y una pista de **dónde mirar**. Tu
entrega es: (1) la línea o líneas que causan el problema, (2) una explicación de dos oraciones,
(3) un arreglo propuesto (no hace falta implementarlo). Dos de los cuatro son bugs reales que
quedaron en el código original; los otros dos son decisiones de diseño con consecuencias.

### A1. El writer que investiga

**Síntoma.** En la UI, un paso titulado "Writer agent: Draft a structured outline based on the
research findings" aparece como `Called research_agent`, y su salida es una lista de fuentes en
vez de un borrador. A veces pasa también con pasos del editor ("Editor agent: Research whether
all citations are complete").

**Dónde mirar.** `src/planning_agent.py`, `executor_agent_step`, el bloque
`# Seleccionar agente basado en el paso`. Leé los `if`/`elif` en orden y pensá qué palabras
contiene el título del paso.

**Para reproducirlo sin API.** Con agentes falsos (truco al final), llamá
`executor_agent_step("Writer agent: Draft based on the research findings.", [], "x")` y mirá
qué agente devuelve.

### A2. El historial que pierde el nombre del agente

**Síntoma.** No se ve en la UI directamente. Se ve en el contexto que recibe cada agente: los
pasos anteriores se clasifican como "Draft", "Feedback", "Research" u "Other", y la rama por
`agent == "writer_agent"` nunca se cumple aunque el writer haya corrido.

**Dónde mirar.** Dos lugares que tienen que coincidir y no coinciden:

- `main.py`, `run_agent_workflow`: la línea `execution_history.append([...])`. Anotá qué hay en
  cada posición.
- `src/planning_agent.py`, `executor_agent_step`: la línea `for i, (desc, agent, output) in
  enumerate(history)`. Anotá con qué nombre se lee cada posición.

Pregunta extra: `executor_agent_step` devuelve tres valores; ¿cuál de los tres se está
descartando en `main.py` sin usarlo para el historial?

### A3. El progreso que desaparece

**Síntoma.** Lanzás una tarea, reiniciás el servidor (o `--reload` lo reinicia solo porque
guardaste un archivo) y `GET /task_progress/{id}` devuelve `{"steps": []}`. `GET /task_status`
sigue diciendo `running` para siempre.

**Dónde mirar.** `main.py`: dónde se define `task_progress` y quién lo escribe. Después,
`get_task_status`: ¿quién pone la tarea en `done`? ¿Ese quién existe todavía después del
reinicio?

### A4. El paso que tumba todo

**Síntoma.** La tarea pasa a `error` en el paso 3 con el mensaje
`Error during execution: Unknown step type: Research & analysis agent: Compile ...`. Los pasos
1 y 2 habían salido bien.

**Dónde mirar.** El `else` final de `executor_agent_step`. Y el `except` de
`run_agent_workflow`: ¿qué hace con los pasos que faltaban? ¿Hay forma de que un paso falle
sin cancelar los siguientes?

## Parte B. Completar código (45 min)

Elegí al menos uno. Los tres se prueban sin correr el workflow completo.

### B1. Evaluar las fuentes después del paso de research

Integrá `evaluar_referencias` del lab 01 en la app. Especificación:

1. Copiá a `app/src/evaluacion.py` las cuatro funciones puras del lab 01 (`extraer_urls`,
   `dominio_de`, `es_dominio_confiable`, `evaluar_referencias`) y una constante
   `DOMINIOS_CONFIABLES` con una lista general (arxiv, acm, ieee, nature, science, nih, nasa,
   wikipedia, .edu de universidades conocidas).
2. En `main.py`, `run_agent_workflow`, después de que `executor_agent_step` devuelve: si
   `agent_name == "research_agent"`, llamá a `evaluar_referencias(output, DOMINIOS_CONFIABLES,
   umbral=0.4)`.
3. Agregá al paso un **segundo substep** con título `Evaluación de fuentes: PASS` o `... FAIL`
   y, como contenido, la tabla de `detalle` en Markdown (URL, dominio, confiable sí/no) más el
   ratio. Fijate cómo está armado el substep existente para usar el mismo formato.
4. En `index.html` no hace falta tocar nada: los substeps se renderizan solos. Verificá que el
   nuevo aparece bajo el paso de research como una fila desplegable más.

Para probar sin API: armá un `history` falso con una salida de research que tenga 3 URLs y
corré solo el bloque nuevo. Después una corrida real.

Pregunta de diseño: ¿qué deberías hacer si da FAIL? ¿Frenar el workflow, reintentar el paso con
un prompt más estricto, o solo informar? Justificalo en un párrafo.

### B2. Reintentos del writer si el texto queda corto

`writer_agent` recibe `min_words_total`, `min_words_per_section` y `retries` y no los usa.
Tiene `_call(messages_)` y `_word_count(md_text)` ya definidos. Completá la lógica:

1. Después de la primera llamada, contá palabras con `_word_count(content)`.
2. Si son menos que `min_words_total` y quedan reintentos, agregá al `messages` un mensaje
   `user` que diga (en español) cuántas palabras tiene, cuántas se esperaban, y que amplíe el
   texto manteniendo las citas; volvé a llamar a `_call`. Repetí hasta `retries` veces.
3. Devolvé el contenido más largo que hayas obtenido (no necesariamente el último).
4. Imprimí en consola cuántos intentos hizo y el conteo final.

`min_words_per_section` podés dejarlo sin usar y documentar por qué (pista: ¿cómo detectarías
las secciones en Markdown?).

Para probar sin API: reemplazá `_call` por una función que devuelva un texto de 100 palabras la
primera vez y 3000 la segunda, y verificá que se llama dos veces con `retries=1`.

### B3. Elegir el modelo desde la request

Agregá a `PromptRequest` un campo `model: str | None = None`. Si viene, se usa para los tres
agentes y el planner (con el prefijo `openai:`); si no, se usan los del `.env`.

Vas a tener que pasar el modelo por: `generate_report` → `planner_agent(..., model=...)` y
`run_agent_workflow(...)` → `executor_agent_step(..., model=...)` → cada agente. Es un ejercicio
de *threading a parameter through*: aburrido, pero es lo que vas a hacer en todo backend.

Validación: si el modelo empieza con `o1`, `o3`, `o4` o `gpt-4o`, devolvé un 400 con un
mensaje en español que explique que esos modelos no están soportados en el material.

Para probar: `curl -X POST .../generate_report -d '{"prompt":"x","model":"gpt-4o"}'` tiene que
dar 400 sin llamar a OpenAI. Con `"model":"gpt-4.1"` tiene que arrancar.

## Parte C. Diseño (15 min, en papel)

### C1. Ruteo con LLM en lugar de palabras clave

Proponé un reemplazo para el bloque de `if "research" in step_lower` que use un LLM para decidir
el agente. Entregá:

1. El prompt (en español) que le mandarías, con el título del paso y la lista de agentes
   disponibles. Pedí que devuelva **solo** uno de tres valores exactos.
2. Cómo validás la respuesta (¿y si devuelve "Writer agent" con mayúscula, o una oración?).
3. Qué hacés si la respuesta no es válida: ¿fallback a palabras clave, `ValueError`, reintentar?
4. El costo: una llamada extra por paso, 6 a 7 por tarea. ¿Vale la pena? ¿En qué caso sí y en
   cuál no? ¿Hay una opción intermedia (por ejemplo, que el planner ya devuelva el agente en
   un campo estructurado)?

Si tenés tiempo, implementalo como `elegir_agente_llm(step_title, model=AI_CHEAP) -> str` y
dejá el ruteo por palabras clave como fallback.

## Truco: probar sin API

Para llamar a `executor_agent_step` o a `run_agent_workflow` sin gastar llamadas, reemplazá los
agentes por funciones falsas antes de llamar:

```python
# desde app/, con OPENAI_API_KEY=x DATABASE_URL=sqlite:///./tasks.db
import src.planning_agent as pa

pa.research_agent = lambda prompt, **kw: ("- https://arxiv.org/abs/1\n- https://blog.com/x", [])
pa.writer_agent = lambda prompt, **kw: ("# Borrador\n\nTexto...", [])
pa.editor_agent = lambda prompt, **kw: ("# Borrador revisado", [])

print(pa.executor_agent_step("Writer agent: Draft based on the research findings.", [], "tema"))
```

Como `main.py` importa las funciones por nombre (`from src.planning_agent import
executor_agent_step`), el parche sobre `pa.research_agent` afecta a `executor_agent_step` porque
ella busca `research_agent` en el módulo `src.planning_agent` en el momento de ejecutarse.

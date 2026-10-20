# Guía de lectura — La app del agente de investigación

**Módulo 4 · Lab 02.** En este lab no escribís un notebook: leés una aplicación real que integra
todo lo que viste en M2, M3 y M4, la corrés, y después la rompés a propósito (`ejercicios.md`).
La app está en `app/` y es el código público de DeepLearning.AI con cambios mínimos para que
corra (ver `app/README.md`).

Recorrido estimado: **60 a 90 minutos**. Leé con la app corriendo al lado: cada sección te dice
qué archivo abrir y qué probar.

## Objetivos

Al terminar vas a poder:

- Seguir una request desde el navegador hasta la base de datos y de vuelta.
- Reconocer en código real los patrones del curso: planner, ejecución paso a paso, agentes
  especializados, tools con `aisuite`, reflexión (editor), persistencia y UI por polling.
- Nombrar las decisiones de diseño que la app tomó y qué costo tiene cada una.
- Encontrar un bug a partir del síntoma que ve el usuario.

## Antes de empezar: quiz de apertura

1. **(Repaso lab 01)** ¿Qué hace que una evaluación sea "a nivel de componente"?
   a) Que la calcule un LLM. b) Que mida un paso aislado del pipeline en vez de la salida final.
   c) Que corra en un servidor.
2. **(Repaso lab 01)** `"notnature.com".endswith("nature.com")` devuelve...
   a) `True`, y por eso se compara con `"." + dominio`. b) `False`. c) Error.
3. **(Nuevo)** En esta app, ¿quién decide qué agente ejecuta cada paso del plan?
   a) El LLM planner, que devuelve el nombre del agente. b) Una función Python que busca
   palabras clave en el título del paso. c) El usuario, desde la UI.
4. **(Nuevo)** ¿Por qué `POST /generate_report` tarda 10 a 30 segundos en responder?
   a) Porque guarda en Postgres. b) Porque ejecuta el planner de forma síncrona antes de
   devolver el `task_id`. c) Porque espera a que termine todo el workflow.
5. **(Base HTTP)** Si el navegador hace `fetch('/task_progress/abc')` cada 2 segundos, eso es...
   a) WebSocket. b) Polling. c) Server-Sent Events.

Las respuestas están en `guia_docente.md`.

## 0. Mapa del territorio (5 min)

```
app/
├─ main.py                 FastAPI: endpoints, modelo Task (SQLAlchemy), thread del workflow
├─ src/
│  ├─ config.py            AI_CHEAP / AI_STRONG desde .env           [agregado para clase]
│  ├─ planning_agent.py    planner_agent() + _ensure_contract() + executor_agent_step()
│  ├─ agents.py            research_agent(), writer_agent(), editor_agent()
│  └─ research_tools.py    arxiv_search_tool, tavily_search_tool, wikipedia_search_tool
├─ templates/index.html    UI: textarea + JS que hace polling
├─ docker/entrypoint.sh    arranca Postgres interno y uvicorn
└─ Dockerfile
```

Tres procesos conviven:

- **El servidor** (uvicorn): recibe requests y las responde.
- **Un thread por tarea**: ejecuta el workflow (planner → research → writer → editor) y va
  actualizando un dict en memoria y una fila en la base.
- **El navegador**: cada 2 segundos pregunta cómo va la tarea y redibuja.

### Diagrama de secuencia

```mermaid
sequenceDiagram
    participant U as Navegador (index.html)
    participant API as FastAPI (main.py)
    participant P as planner_agent
    participant T as Thread run_agent_workflow
    participant E as executor_agent_step
    participant A as research / writer / editor
    participant DB as DB (tasks)

    U->>API: POST /generate_report {prompt}
    API->>DB: INSERT Task(status="running")
    API->>P: planner_agent(prompt)  [síncrono, 10-30 s]
    P-->>API: lista de 6-7 títulos de pasos (_ensure_contract)
    API->>T: threading.Thread(...).start()
    API-->>U: {"task_id"}
    loop cada 2 s
        U->>API: GET /task_progress/{id}
        API-->>U: steps (dict en memoria)
        U->>API: GET /task_status/{id}
        API-->>U: status + result (DB)
    end
    loop por cada paso del plan
        T->>E: executor_agent_step(título, history, prompt)
        E->>E: elegir agente por palabras clave
        E->>A: agente(prompt enriquecido con el historial)
        A-->>E: texto (research usa tools con aisuite)
        E-->>T: (título, agente, salida)
        T->>T: history.append([...]); task_progress[id] actualizado
    end
    T->>DB: UPDATE Task status="done", result=json
```

Abrí la app, mandá un prompt corto y, mientras corre, seguí las secciones de abajo.

## 1. La entrada: `main.py`, endpoints (10 min)

Abrí `app/main.py`.

**Qué mirar.**

- Las primeras 40 líneas: `load_dotenv`, `DATABASE_URL`, el modelo `Task`. Fijate que `result`
  es un `Text` con JSON adentro, no columnas separadas. Es la decisión más simple posible y
  alcanza para esta app.
- `task_progress = {}`: un dict global en memoria. Acá vive el progreso paso a paso. Pregunta
  para vos: ¿qué pasa con este dict si reiniciás el servidor con una tarea a medio correr?
  ¿Y si corrés dos workers de uvicorn?
- `PromptRequest`: el body que acepta el `POST`. Tiene un solo campo. En `ejercicios.md` vas a
  agregarle `model`.
- `generate_report`: leé las 20 líneas en orden. Primero inserta la tarea, después llama al
  planner **y espera**, después arma `task_progress[task_id]`, después lanza el thread y recién
  ahí devuelve. El usuario ve el spinner "Generating steps" durante todo el planner.
- `get_task_progress` lee del dict; `get_task_status` lee de la base. Dos fuentes de verdad.

**Probá.** Con la app corriendo: `curl localhost:8000/task_progress/cualquier-cosa` devuelve
`{"steps": []}` sin error; `curl localhost:8000/task_status/cualquier-cosa` devuelve 404. ¿Por
qué se comportan distinto?

## 2. El plan: `planner_agent` y `_ensure_contract` (15 min)

Abrí `app/src/planning_agent.py`, función `planner_agent`.

**Para qué.** El planner convierte el prompt del usuario en una lista de pasos. Es el patrón
*planning* del curso: un LLM decide la secuencia, el código la ejecuta.

**Qué mirar.**

- El prompt pide una **lista de Python de strings** (no JSON, no Markdown). Y le dicta
  literalmente cuál tiene que ser el primer paso, el segundo y el último. ¿Para qué pedirle a
  un LLM que planifique si vas a fijarle la mitad del plan? Respuesta: para que el plan sea
  predecible donde importa (siempre buscar primero, siempre escribir al final) y flexible en
  el medio.
- `_coerce_to_list`: intenta `json.loads`, después `ast.literal_eval`, después quita el
  code fence. Es la validación explícita de la salida del LLM que piden las convenciones. Si
  todo falla, devuelve `[]`.
- `_ensure_contract`: **el contrato**. Si la lista está vacía, usa un plan por defecto de 6
  pasos. Si no está vacía, fuerza el primer paso, el segundo y el último, y tira cualquier paso
  de arXiv que no esté "atado" al de Tavily. Leé esa list comprehension en voz alta:
  `s for s in steps_list[1:] if "arXiv" not in s or "For each collected item" in s`.
- `[:7]`: tope de 7 pasos. Cada paso es al menos una llamada al modelo.

**Patrón del curso.** Planning + "defensive parsing": nunca confiar en que el modelo devolvió lo
que pediste. El contrato es la red de seguridad.

**Probá.** Pedí un prompt raro ("hola") y mirá qué plan sale. Después uno muy específico. ¿Los
pasos 1, 2 y último son siempre iguales?

## 3. La ejecución: `executor_agent_step` (15 min)

Misma archivo, función `executor_agent_step`. Es la función más importante del lab.

**Qué mirar.**

- **El contexto.** Recorre `history` y arma un texto con secciones "Draft", "Feedback",
  "Research" u "Other" según palabras clave en `desc` o el valor de `agent`. Después pega el
  título del paso actual. Eso es todo lo que el agente del paso N sabe de los pasos anteriores.
- **El `for i, (desc, agent, output) in enumerate(history)`.** Desarma cada entrada del
  historial en tres nombres. Anotá esos tres nombres y volvé a `main.py`, línea
  `execution_history.append([plan_step_title, actual_step_description, output])`. ¿Coinciden
  las posiciones con los nombres? Anotá tu respuesta; va a ser parte de la caza de bugs.
- **El ruteo.** `if "research" in step_lower` → research; `elif "draft" ... or "write"` →
  writer; `elif "revise" ... or "edit" ... or "feedback"` → editor; sino `ValueError`. Es un
  router por palabras clave: barato, determinista, y frágil. Pensá en un título de paso que
  el planner podría generar y que caería en el agente equivocado.

**Patrón del curso.** Ejecución paso a paso con historial acumulado (lo mismo que hacías a mano
en M3, pero con tres agentes). El ruteo es el punto donde el patrón *routing* de M5 aparece en
su versión más primitiva.

## 4. Los agentes: `agents.py` (10 min)

Abrí `app/src/agents.py`.

**`research_agent`.** Es `buscar_referencias` del lab 01 con un prompt más largo. Fijate:

- `tools=[arxiv_search_tool, tavily_search_tool, wikipedia_search_tool]`, `max_turns=5`,
  `temperature=0.0`. `aisuite` arma el schema desde los docstrings y ejecuta el loop.
- Después de la llamada recorre `resp.intermediate_responses` e `intermediate_messages` para
  listar qué tools se llamaron y con qué argumentos, y pega esa lista como HTML al final del
  texto. Es lo que ves en la UI como "Tools used".
- `Today is ...` en el prompt: igual que en el lab 01.

**`writer_agent`.** Un system prompt largo (estructura obligatoria, citas numéricas) y una
llamada. Mirá la firma: `min_words_total`, `min_words_per_section`, `retries`. Después mirá el
cuerpo: define `_call` y `_word_count`... y llama a `_call` una sola vez. Los tres parámetros no
se usan. Alguien empezó a implementar reintentos y no terminó. En `ejercicios.md` lo terminás vos.

**`editor_agent`.** Es la *reflexión* de M2: recibe el borrador y devuelve una versión mejorada.
Una sola llamada, sin tools.

**Patrón del curso.** Agentes especializados con prompts distintos y el mismo cliente. Research
usa tools (M3); editor es reflexión (M2).

## 5. Las tools: `research_tools.py` (5 min)

Abrí `app/src/research_tools.py`. Son las mismas tres tools del lab 01 con dos diferencias:

- `arxiv_search_tool` **descarga el PDF** de cada paper y reemplaza el resumen por las primeras
  6 páginas de texto extraído. Más contexto para el writer, pero mucho más lento (por eso
  existe `ARXIV_FETCH_PDF=0`).
- Las tres devuelven `[{"error": "..."}]` en vez de levantar excepciones. ¿Por qué? Porque la
  excepción cortaría el loop de `aisuite`; un dict con error le permite al modelo leerlo y
  decidir qué hacer (reintentar con otra query, usar otra tool).

## 6. Persistencia y el thread: `run_agent_workflow` (10 min)

Volvé a `app/main.py`, función `run_agent_workflow`.

**Qué mirar.**

- `update_step_status`: modifica `steps_data` (que es una referencia a
  `task_progress[task_id]["steps"]`). Es lo que lee `/task_progress`.
- El `for i, plan_step_title in enumerate(initial_plan_steps)`: por cada paso llama a
  `executor_agent_step`, agrega al historial, y arma un **substep en HTML** con el prompt, el
  paso anterior, la tarea y la salida. Ese HTML viaja en JSON hasta el navegador, que lo pasa
  por `marked.parse` y lo inyecta con `innerHTML`.
- Al final: `final_report_markdown = execution_history[-1][-1]`. El reporte final es,
  literalmente, la salida del último paso. Si el planner puso al editor último, el reporte es
  lo que devolvió el editor.
- El `except`: marca el paso que estaba `running` como `error` y la tarea como `error`. Pero
  mirá qué pasa si `executor_agent_step` levanta `ValueError("Unknown step type")`: el
  workflow entero se cae por un título de paso que no matcheó ninguna palabra clave.

**Patrón del curso.** Estado en dos lugares: memoria (progreso fino, volátil) y DB (resultado
final, durable). Es un trade-off consciente: escribir cada substep en la DB sería más robusto
y más lento.

## 7. La UI: polling en `index.html` (5 min)

Abrí `app/templates/index.html`, bajá al `<script>`.

- `submitPrompt`: `fetch('/generate_report')`, guarda `task_id`, arranca
  `setInterval(fetchProgress, 2000)`.
- `fetchProgress`: pide `/task_progress`, redibuja solo los pasos cuya clave
  `${title}-${status}-${substeps.length}` cambió, y después llama a `fetchTaskStatus`.
- `fetchTaskStatus`: pide `/task_status`; si `done` o `error`, corta el intervalo. Si hay
  `html_report`, lo renderiza con `marked`.

Dos cosas para notar: el HTML de los substeps y del reporte se inyecta sin sanitizar
(`innerHTML`), y el servidor tiene `CORSMiddleware(allow_origins=["*"])`. Para una app que
corre en `localhost` con un solo usuario está bien; para cualquier otra cosa, no.

## 8. Qué patrones del curso integra (resumen)

| Patrón | Dónde está en la app | Módulo donde lo viste |
|---|---|---|
| Reflexión | `editor_agent` revisa el borrador del writer | M2 |
| Tools / function calling con `aisuite` | `research_agent` + `research_tools.py` | M3 |
| Planning con contrato | `planner_agent` + `_ensure_contract` | M4 (clase) |
| Validación defensiva de salidas del LLM | `_coerce_to_list` | M2–M4 |
| Routing (versión mínima, por palabras clave) | `executor_agent_step` | M5 (anticipo) |
| Agentes especializados con historial compartido | `agents.py` + `execution_history` | M5 (anticipo) |
| Evaluación de componente | **No está.** Es el ejercicio 1 de `ejercicios.md` | M4 lab 01 |
| Persistencia + API + UI | `main.py` + `index.html` | M3 (servidor de email) |

## 9. Para cerrar

Tres preguntas antes de pasar a `ejercicios.md`:

1. Si tuvieras que agregar la evaluación del lab 01 a esta app, ¿después de qué línea de qué
   archivo la pondrías? ¿Qué harías si da FAIL: frenar, avisar o reintentar?
2. El historial que recibe cada agente es texto plano concatenado. ¿Qué tamaño puede llegar a
   tener en el paso 7? ¿Qué problema trae eso?
3. ¿Qué parte de esta app reescribirías primero si tuviera que atender a 50 usuarios a la vez?

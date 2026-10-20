# Guía docente — La app del agente de investigación

## Ficha

| | |
|---|---|
| **Duración** | 70 min (bloque 2 de la sesión de M4, después del lab 01). Si se hacen los tres ejercicios de código, 150 min: ver "Secuencia" para la variante en dos sesiones. |
| **Prerrequisitos** | Lab 01 de M4 (la evaluación que se integra en B1). M3 completo (function calling, `aisuite`, el servidor FastAPI del email assistant). Haber visto un `fetch` en JS alguna vez ayuda, no es obligatorio. |
| **Keys** | `OPENAI_API_KEY` para correr la app. `TAVILY_API_KEY` opcional (fallback a Wikipedia). La lectura y la caza de bugs funcionan **sin ninguna key** (truco de los agentes falsos en `ejercicios.md`). |
| **Archivos** | `guia_lectura.md`, `ejercicios.md`, esta guía, `app/` (código adaptado + `app/README.md` con cómo correrla). No hay notebook. |
| **Costo estimado** | Una corrida completa = 1 llamada al planner (`MODEL_STRONG`) + 6 a 7 pasos con `MODEL_CHEAP`; el paso de research hace 2 a 5 llamadas por el loop de tools. Total 8 a 12 llamadas al modelo por corrida, 2 a 6 minutos. El writer genera hasta 15 000 tokens de salida (`max_tokens=15000`): es el paso más caro. **Recomendación:** una corrida del profesor proyectada + una por grupo de 3 o 4, no una por alumno. |
| **Se evalúa** | Entrega escrita de la caza de bugs (A1 a A4) y al menos un ejercicio de código. Rúbrica abajo. |

## Secuencia sugerida (70 min, bloque 2 de la sesión)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–5 | Quiz de apertura. Las dos primeras repasan el lab 01. | Profesor |
| 5–10 | Arrancar la app proyectada (`uvicorn`, sqlite, `ARXIV_FETCH_PDF=0`) y mandar un prompt. Mientras corre, abrir `guia_lectura.md` §0 y el diagrama de secuencia. | Profesor en vivo |
| 10–20 | Recorrido guiado de `main.py` (§1) y `planner_agent` + `_ensure_contract` (§2). Volver a la pestaña de la app para ver los pasos que generó el planner. | Profesor |
| 20–35 | `executor_agent_step` (§3) **en detalle**. Es la función del bug A1 y A2. Hacer que lean en voz alta los `if/elif` y la línea del `for ... (desc, agent, output)`. No revelar todavía. | Profesor + alumnos |
| 35–45 | `agents.py`, `research_tools.py`, `run_agent_workflow`, `index.html` (§4 a §7), más rápido. La corrida proyectada ya terminó: mostrar el reporte final y los substeps expandidos. | Profesor |
| 45–65 | Caza de bugs A1 a A4 en grupos, con agentes falsos (sin API). Cada grupo entrega línea + explicación + arreglo propuesto. | Alumnos |
| 65–70 | Puesta en común de A1 y A2. Las partes B y C quedan para la casa o para una sesión extra. | Todos |

### Variante en dos sesiones

Si el grupo viene flojo de Python o querés hacer los ejercicios de código en clase:

- **Sesión A (3 h):** lab 01 completo (100 min) + lectura de la app §0 a §3 (50 min) + caza de
  bugs A1 y A2 (30 min).
- **Sesión B (3 h):** lectura §4 a §8 (30 min) + A3 y A4 (20 min) + B1 (evaluación de fuentes,
  60 min) + B2 o B3 a elección (45 min) + C1 en papel y cierre (25 min).

La sesión B es la que más vale si el bootcamp tiene un módulo posterior de backend: B1 y B3 son
exactamente el tipo de cambio que van a hacer en un proyecto real.

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

- **En vivo (profesor):** la única corrida completa proyectada. Lanzarla al minuto 5 para que
  termine antes de llegar a §6. Tener a mano un `task_id` de una corrida anterior guardado en
  sqlite por si la red falla (`task_status` lo devuelve igual).
- **Alumnos:** leer con la app corriendo en su máquina pero **sin lanzar tareas** hasta la caza
  de bugs, y ahí con agentes falsos. Si cada alumno lanza una corrida "para ver", son 25 × 10
  llamadas más 25 × 15 000 tokens de salida del writer.
- **Si no hay red o no hay keys:** todo el lab funciona igual salvo la corrida proyectada. Usar
  el `tasks.db` de una corrida previa (dejarlo preparado) y mostrar el JSON de `result`.

## Riesgos de correrla en clase (leer antes de la sesión)

1. **Costo por corrida.** 8 a 12 llamadas, de las cuales el writer puede devolver 3 000 palabras
   (hasta 15 000 tokens de salida). Con `gpt-4.1-mini` una corrida sale centavos; con
   `MODEL_STRONG` en los agentes (si alguien cambia el `.env`) sale diez veces más. Fijar la
   regla: una corrida por grupo.
2. **Límites de Tavily si se comparte la key.** El plan gratuito de Tavily es de 1 000 créditos
   al mes y cada búsqueda consume 1 (básica) o 2 (avanzada). Una corrida hace 1 a 3 búsquedas
   Tavily. Con 25 alumnos lanzando 2 corridas cada uno se consumen 50 a 150 créditos en una
   clase; es manejable, pero si la misma key se usa en M3 y M5 se agota. Alternativa: no
   repartir la key y dejar que la tool caiga a Wikipedia (lo avisa en el campo `source`).
3. **Límites de arXiv.** La API pública pide no más de una request cada 3 segundos por IP. Si
   toda el aula sale por la misma IP y 25 personas lanzan research a la vez, arXiv devuelve 429
   o 503 y la tool devuelve `[{"error": ...}]`. La sesión HTTP tiene reintentos con backoff,
   así que suele recuperarse, pero el paso de research tarda más. Con `ARXIV_FETCH_PDF=1`
   además se descargan 3 PDFs por búsqueda: **poner `ARXIV_FETCH_PDF=0` en clase**.
4. **XSS y CORS: solo local.** `CORSMiddleware(allow_origins=["*"])` y el frontend inyecta con
   `innerHTML` el HTML que devuelven los agentes (que a su vez incluye texto de páginas web).
   Una página maliciosa que el agente cite podría meter `<script>` en el reporte y ejecutarlo
   en el navegador del usuario. En `localhost` con un solo usuario es un riesgo teórico; **no
   desplegarla en una URL pública ni exponerla en la red del aula**. Si alguien pregunta, es un
   buen ejemplo de por qué el ejercicio B1 conviene hacerlo en el servidor y no en el JS.
5. **Lentitud del planner síncrono.** `POST /generate_report` no responde hasta que el planner
   termina (10 a 30 s con `gpt-4.1`). El navegador muestra el spinner y nada más; los alumnos
   van a pensar que se colgó. Avisarlo antes. Es el bug de diseño que motiva C1 y el ejercicio
   de mover el planner al thread.
6. **`--reload` reinicia y pierde el progreso.** Si un alumno guarda un archivo mientras corre
   una tarea, uvicorn reinicia, `task_progress` se vacía y la tarea queda `running` para
   siempre en la DB (bug A3). Decirles que no editen con una tarea en curso, o que corran sin
   `--reload`.
7. **Postgres publicado.** El README original mandaba `-p 5432:5432` con usuario `app` y clave
   `local`. Nuestro Dockerfile solo expone el 8000. Si algún alumno copia el comando del repo
   original, su Postgres queda abierto en la red del aula con credenciales conocidas.
8. **`RESET_DB`.** Si queda en `1` en el `.env`, cada reinicio borra las tareas. El original lo
   hacía siempre; acá es opt-in, pero conviene chequear el `.env` antes de proyectar.

## Dónde se traban (y qué decir)

1. **"No entiendo qué hace `_ensure_contract`."** Pedirles que escriban una lista de 3 pasos
   inventados y la pasen a mano por la función. Ver que termina con 5 (dos forzados al
   principio, uno al final). La list comprehension del medio: leerla como "dejá los pasos que
   no mencionan arXiv, o que lo mencionan pero están atados a la lista de Tavily".
2. **Confunden `task_progress` (dict) con la tabla `tasks` (DB).** Dibujar las dos cajas en el
   pizarrón: una se borra al reiniciar, la otra no. Preguntar qué endpoint lee cada una.
3. **No ven el bug A2 aunque lo tengan adelante.** Hacerlos escribir en dos renglones:
   `append([plan_step_title, actual_step_description, output])` y
   `(desc, agent, output)`. Posición 2: `actual_step_description` vs. `agent`. Y recordar que
   `executor_agent_step` devuelve `step_title` dos veces (como primer valor y como
   "descripción"), así que posición 1 y 2 son el mismo string.
4. **Creen que `elif "draft" in step_lower or "write"` tiene un bug de precedencia.** No: es
   `("draft" in step_lower) or ("write" in step_lower)`, está bien. El bug es el orden de los
   `if`, no la expresión.
5. **El truco de los agentes falsos no les funciona** porque hacen `from src.planning_agent
   import executor_agent_step` y después parchean `pa.research_agent`. Funciona igual: la
   función busca `research_agent` en el módulo al ejecutarse. Si no funciona, es porque
   parchearon `src.agents.research_agent` en vez de `src.planning_agent.research_agent`
   (el `from ... import` ya copió la referencia).
6. **En B1 intentan evaluar en el JS.** Explicar que la evaluación es parte del pipeline y tiene
   que quedar guardada con el resultado; además en el servidor tenés las funciones del lab 01.
7. **En B3 no saben por dónde pasar el parámetro.** Dibujar la cadena de llamadas de la guía
   §0 y marcar cada función que tiene que recibir `model`. Son cinco firmas.

## Respuestas del quiz de apertura

1. **b**. Medir un paso aislado (la búsqueda) en vez del reporte final.
2. **a**. `endswith("nature.com")` acepta `notnature.com`; por eso la comparación es contra
   `"." + dominio` (o igualdad exacta).
3. **b**. `executor_agent_step` busca "research", "draft"/"write", "revise"/"edit"/"feedback"
   en el título. El planner no devuelve el agente de forma estructurada.
4. **b**. `generate_report` llama a `planner_agent` y espera; recién después lanza el thread y
   devuelve el `task_id`.
5. **b**. Polling: el cliente pregunta periódicamente. WebSocket y SSE son push del servidor.

## Soluciones de la caza de bugs (Parte A)

### A1. El writer que investiga (bug real)

**Causa.** En `executor_agent_step`, el primer `if` es `if "research" in step_lower`. Un paso
del writer que diga "based on the research findings" contiene "research", así que entra ahí
antes de llegar al `elif "draft" ... or "write"`. Lo mismo con el editor: "Research whether
citations..." va a research.

**Reproducir.** `executor_agent_step("Writer agent: Draft based on the research findings.", [], "x")`
devuelve `"research_agent"` (probado con agentes falsos).

**Arreglos posibles, de menos a más robusto:**

1. Reordenar: chequear primero el prefijo del título. El planner siempre escribe "Research
   agent:", "Writer agent:", "Editor agent:" al principio:
   ```python
   if step_lower.startswith("research agent"):
       ...
   elif step_lower.startswith("writer agent"):
       ...
   elif step_lower.startswith("editor agent"):
       ...
   ```
   Con fallback a las palabras clave si el prefijo no está.
2. Hacer que el planner devuelva estructura: una lista de `{"agent": "writer", "task": "..."}`
   en JSON, y rutear por el campo `agent`. Elimina el problema de raíz; es la "opción
   intermedia" de C1.
3. Ruteo con LLM (C1). Más caro, más flexible.

### A2. El historial que pierde el nombre del agente (bug real)

**Causa.** `main.py` guarda `[plan_step_title, actual_step_description, output]`. Como
`executor_agent_step` devuelve `step_title` como primer valor **y** como "descripción", las
posiciones 0 y 1 son el mismo string. El `agent_name` que devuelve en segundo lugar se usa
para el substep de la UI (`f"Called {agent_name}"`) pero **no** se guarda en el historial.

`executor_agent_step` lee cada entrada como `(desc, agent, output)`: `agent` recibe el título
del paso, nunca `"writer_agent"`. Las ramas `or agent == "writer_agent"` etc. nunca se cumplen
y la clasificación del contexto depende solo de las palabras clave del título ("draft",
"feedback", "research"). Un paso del writer titulado "Generate the final report" cae en
"Other".

**Arreglo.** En `main.py`:
```python
execution_history.append([actual_step_description, agent_name, output])
```
y en `format_history` ajustar el desempaquetado (`for desc, agent, output in history`), que
hoy también asume `(title, desc, output)`. Mejor aún: usar un dict
`{"titulo": ..., "agente": ..., "salida": ...}` y leer por nombre en los dos lados; así el
orden deja de importar.

### A3. El progreso que desaparece (decisión de diseño)

**Causa.** `task_progress = {}` vive en memoria del proceso. Al reiniciar (incluido el
`--reload`), se vacía: `get_task_progress` devuelve `{"steps": []}`. El thread que iba a poner
la tarea en `done` murió con el proceso, así que la fila queda en `running`.

**Arreglos.** (1) Al arrancar, marcar como `error` toda tarea que esté en `running` (no puede
haber ninguna legítimamente en curso en un proceso nuevo). (2) Guardar `steps` en la DB
(columna JSON) en cada `update_step_status`, y que `/task_progress` lea de ahí. (3) Para
producción: una cola de trabajos (Celery, RQ, arq) en vez de `threading.Thread`, y un worker
separado del servidor web. Preguntar: ¿qué pasa con dos workers de uvicorn? Cada uno tiene su
propio dict; el `/task_progress` puede caer en el worker equivocado.

### A4. El paso que tumba todo (decisión de diseño)

**Causa.** El `else` de `executor_agent_step` levanta `ValueError("Unknown step type")`. El
`except` de `run_agent_workflow` captura cualquier excepción, marca el paso como `error`, pone
la tarea en `error` y **sale del `for`**: los pasos siguientes no se ejecutan. Un título como
"Research & analysis agent: Compile..." sí matchea "research"; uno como "Synthesize the
collected evidence" no matchea nada y tumba la tarea.

**Arreglos.** (1) Fallback en el `else`: si el paso no se reconoce, mandarlo al writer (o al
agente del paso anterior) y loguear un warning, en vez de levantar. (2) Mover el `try/except`
adentro del `for`, por paso: marcar ese paso como `error`, guardar un output tipo
`"[paso omitido: ...]"` y seguir. (3) Combinar con A1: si el ruteo es por prefijo o
estructurado, los títulos no reconocidos casi desaparecen.

## Soluciones de los ejercicios de código (Parte B, esbozo)

### B1. Evaluar las fuentes después del research

```python
# main.py, dentro del for de run_agent_workflow, después de executor_agent_step
from src.evaluacion import evaluar_referencias, DOMINIOS_CONFIABLES

if agent_name == "research_agent":
    ev = evaluar_referencias(output, DOMINIOS_CONFIABLES, umbral=0.4)
    estado = "PASS" if ev["aprobado"] else "FAIL"
    filas = "\n".join(
        f"| {url} | {dominio} | {'sí' if ok else 'no'} |" for url, dominio, ok in ev["detalle"]
    )
    tabla = "| URL | Dominio | Confiable |\n|---|---|---|\n" + (filas or "| (sin URLs) | | |")
    update_step_status(
        i, "done", None,
        {"title": f"Evaluación de fuentes: {estado}",
         "content": f"**{ev['confiables']} de {ev['total']}** URLs confiables (ratio {ev['ratio']:.0%}).\n\n{tabla}"},
    )
```
`update_step_status` acepta `description=""` para no pisar la descripción; pasarle `None` o
`""`. El substep aparece solo en la UI porque el JS itera `step.substeps`.

Sobre qué hacer con FAIL: para la clase, informar. Reintentar el paso con un prompt más
estricto es razonable (una vez); frenar el workflow no, porque el usuario prefiere un reporte
con fuentes flojas marcadas a ningún reporte.

### B2. Reintentos del writer

```python
content = _call(messages)
mejor = content
intentos = 0
while _word_count(mejor) < min_words_total and intentos < retries:
    intentos += 1
    messages.append({"role": "assistant", "content": mejor})
    messages.append({"role": "user", "content": (
        f"El reporte tiene {_word_count(mejor)} palabras y se esperaban al menos {min_words_total}. "
        "Ampliá cada sección con más análisis y ejemplos, manteniendo todas las citas y la sección de referencias. "
        "Devolvé el reporte completo.")})
    nuevo = _call(messages)
    if _word_count(nuevo) > _word_count(mejor):
        mejor = nuevo
print(f"Writer: {intentos} reintento(s), {_word_count(mejor)} palabras")
return mejor, messages
```
`min_words_per_section` queda sin usar: para implementarlo habría que partir el Markdown por
`## ` y contar cada bloque; es un buen ejercicio extra pero el formato de los títulos que
devuelve el modelo no es estable.

### B3. Modelo desde la request

```python
class PromptRequest(BaseModel):
    prompt: str
    model: str | None = None

MODELOS_NO_SOPORTADOS = ("o1", "o3", "o4", "gpt-4o")

@app.post("/generate_report")
def generate_report(req: PromptRequest):
    if req.model and req.model.startswith(MODELOS_NO_SOPORTADOS):
        raise HTTPException(400, f"El modelo {req.model!r} no está soportado en este material; usá gpt-4.1 o gpt-4.1-mini.")
    modelo = f"openai:{req.model}" if req.model else None
    ...
    initial_plan_steps = planner_agent(req.prompt, model=modelo or AI_STRONG)
    thread = threading.Thread(target=run_agent_workflow, args=(task_id, req.prompt, initial_plan_steps, modelo))
```
Y `run_agent_workflow(..., modelo=None)` → `executor_agent_step(..., model=modelo)` →
`research_agent(prompt=..., model=model or AI_CHEAP)` etc. Cinco firmas tocadas.

### C1. Ruteo con LLM (puntos a esperar)

- Prompt: "Dado este paso de un plan de investigación, respondé con una sola palabra, exactamente
  `research`, `writer` o `editor`: cuál agente lo ejecuta. Paso: ...".
- Validación: `.strip().lower()`, comparar contra el set de tres; si no está, fallback a las
  palabras clave y warning. Nunca `ValueError` directo.
- Costo: 6 a 7 llamadas extra por tarea con `MODEL_CHEAP`. Vale cuando los títulos del plan
  son libres; no vale si el planner ya puede devolver el agente estructurado (la opción
  intermedia, que es la mejor respuesta).

## Rúbrica

| Criterio | Puntos |
|---|---|
| A1 y A2: identifican la línea exacta y explican la causa en dos oraciones | 30 |
| A3 y A4: distinguen "bug" de "decisión de diseño" y proponen un arreglo razonable | 20 |
| Un ejercicio B completo que corre (con agentes falsos o con API) | 35 |
| C1 en papel: prompt + validación + análisis de costo | 15 |

## Diferencias con el material original de DeepLearning.AI

El original es un repo público para "probar" el agente, sin material didáctico. Acá se usa
como caso de lectura y caza de bugs. Cambios en el código (todos marcados `# [Adaptación
clase]`; lista completa en `app/README.md`):

| Original | Acá | Por qué |
|---|---|---|
| `"openai:o4-mini"` (planner) y `"openai:gpt-4.1-mini"` hardcodeados en cada función | `src/config.py` lee `MODEL_CHEAP` / `MODEL_STRONG` del `.env` | Convención del material; `o4-mini` retirado |
| `DATABASE_URL.startswith(...)` antes del chequeo de `None` → `AttributeError` | `RuntimeError` con mensaje en español y las dos opciones (sqlite / Postgres) | Error claro para alumnos junior |
| `drop_all` en cada arranque | Solo con `RESET_DB=1` | Perdía las tareas en cada reinicio |
| Solo Postgres | sqlite con `check_same_thread=False` | Correr sin Docker en clase |
| `TemplateResponse("index.html", {"request": request})` | `TemplateResponse(request, "index.html", {})` | Falla con Starlette actual |
| `import wikipedia` (paquete abandonado) | API de MediaWiki con `requests` | No disponible en Python 3.12+ |
| Tavily sin key → `ValueError`, paso entero falla | Fallback a Wikipedia con aviso en `source` | Clase sin key de Tavily |
| `research_tools.py` con imports repetidos 5 veces y PDFs siempre | Un bloque de imports; `ARXIV_FETCH_PDF=0` para apagar PDFs | Legibilidad y velocidad en clase |
| `requirements.txt` sin versiones, con duplicados | Versiones mínimas alineadas con la raíz del material | Reproducibilidad |
| `EXPOSE 8000 5432` y README con `-p 5432:5432` | Solo 8000 | No exponer Postgres con `app:local` en la red del aula |
| Logos de DeepLearning.AI, arXiv, Tavily, Wikipedia en `static/` | No se copiaron | Imágenes con marca (brief) |
| Texto de la UI "powered by GPT-4.1-mini and o4-mini" | "models set in .env" | Coherencia con el cambio 1 |

**Lo que se dejó intacto a propósito** (material de la caza de bugs): el ruteo por palabras
clave con "research" antes que "write" (A1), el historial guardado como `(título, descripción,
salida)` y leído como `(desc, agent, output)` (A2), `task_progress` en memoria (A3), el
`ValueError` que tumba el workflow (A4), los parámetros sin usar de `writer_agent` (B2),
`PromptRequest` con un solo campo (B3), el planner síncrono y el CORS abierto (riesgos 4 y 5).

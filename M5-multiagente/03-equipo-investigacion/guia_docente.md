# Guía docente — Equipo de investigación (M5 · Lab 03)

## Ficha

- **Duración:** 100 minutos (primera parte de la sesión 2 del módulo). El resto de la
  sesión va al proyecto de cierre (ver `README.md` del módulo).
- **Prerrequisitos:** M3 (tools con aisuite: `tools=[funciones]`, `max_turns`), M4
  (`research_tools` ya usado), labs 01 y 02 de M5 (patrón planner/executor).
- **Keys:** `OPENAI_API_KEY` obligatoria. `TAVILY_API_KEY` opcional (sin ella,
  `tavily_search_tool` cae a Wikipedia y lo avisa). Hace falta **red** para arXiv y Wikipedia.
- **Archivos:** `lab.py` → notebooks, `research_tools.py` (copia de `comun/`), `utils.py`,
  `tests.py`, `pytest.ini`, `workbook.md`, `data/` (vacía; ahí se guarda `informe.md`).
- **Modelos:** `AI_STRONG` para planner y editor; `AI_CHEAP` para research, writer y ruteo.
- **Costo estimado:** **15 a 25 llamadas por corrida completa** (1 planner + por paso:
  1 ruteo + 1 agente + hasta 6 vueltas de tools en Research). Las pruebas rápidas sueltas
  suman ~6 más. `PLAN_CORTO` cuesta 8 a 10.

> **Advertencia de costo.** Este es el lab más caro del material. Recomendación: el profesor
> corre el pipeline completo (sección 7) **una sola vez en vivo**, proyectado. Los alumnos
> desarrollan y prueban sobre `PLAN_CORTO` (3 pasos) y validan con `run_all`, que usa un
> cliente simulado y no gasta llamadas. Si la clase es grande (>15 personas), pedir que
> solo la mitad corra la sección 7 en casa.

## Secuencia sugerida (100 min)

| Min | Qué | Cómo |
|---|---|---|
| 0–5 | Quiz de apertura | Las preguntas 1 y 2 repasan la sesión anterior (labs 01 y 02). |
| 5–15 | Teoría: equipo de roles, el executor como router, el historial | Dibujar el diagrama de la sección 1. Comparar con M3 ("un agente que hacía todo"). |
| 15–22 | Sección 2: tools y schema de aisuite | Mostrar el schema generado desde el docstring. Decir por qué las queries van en inglés. |
| 22–27 | Sección 3: ejemplo resuelto `agente_resumidor` | "Todos los agentes son esto con otro system prompt". |
| 27–40 | Huecos 1–2: planner | Insistir en `eval()` vs `json.loads`. Correr una vez con `TEMA` y leer el plan en voz alta. ¿Es atómico? ¿El último paso es el informe? |
| 40–55 | Huecos 3–4: research | Correr la prueba rápida. Mirar `tools usadas: N`. Abrir `response.choices[0].intermediate_messages` en una celda aparte para ver el loop. |
| 55–62 | Huecos 5–6: writer y editor | Son copias del ejemplo resuelto con otro system. |
| 62–80 | Huecos 7–8: executor | Correr con `PLAN_CORTO`. Leer el log. Mostrar que el Writer del paso 2 menciona lo que encontró el Research del paso 1. |
| 80–85 | `run_all` | Explicar que inyecta un cliente falso: 0 llamadas. |
| 85–100 | Sección 7 en vivo (una vez) | Proyectar. Mientras corre, discutir cuántas llamadas van. Abrir `data/informe.md` al final. |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

- **En vivo:** teoría, schema de aisuite, la corrida del planner (para que todos trabajen
  sobre el mismo plan), y la sección 7 completa.
- **Alumnos:** los 8 huecos y las pruebas rápidas. Pedirles que **no** corran la sección 7
  hasta que `run_all` pase.
- Si hay poco tiempo: dar resueltos writer y editor (huecos 5 y 6) y concentrarse en
  planner, research y executor.

## Dónde se traban (y qué decir)

1. **El planner devuelve `{"plan": [...]}` o `{"steps": [...]}`.** El `ValueError` del hueco
   2 lo dice. Opciones: reforzar el prompt, o aceptar el dict con una sola lista adentro
   (está en la extensión). Mejor momento para hablar de "contratos de salida".
2. **`research_agent` en vez de `agente_research` al rutear.** El modelo traduce. El
   `ValueError` muestra los válidos. Agregar "copiá el nombre exactamente" al prompt de ruteo.
3. **`tools usadas: 0`.** La tarea no pedía buscar o el modelo "ya sabía". Mostrar que sin
   tool no hay URL real: pedir "usá al menos una tool" en la tarea o en el system.
4. **Confunden `max_turns` con cantidad de tools.** Es cantidad de vueltas del loop; en una
   vuelta el modelo puede pedir varias tools. Mirar `intermediate_messages` lo aclara.
5. **El contexto crece y el Writer "se olvida" de las fuentes.** Con 5 pasos no pasa, pero
   es la pregunta correcta: anticipa la extensión de historial acotado.
6. **Red bloqueada / proxy.** Las tools levantan `ProxyError`; aisuite la devuelve al modelo
   como resultado de la tool, y el modelo suele decir "no pude buscar". Probar la celda de
   la sección 2 antes de empezar.
7. **Corren la sección 7 varias veces "para ver si mejora".** Cada corrida son 20 llamadas.
   Pedir que experimenten con `PLAN_CORTO`.
8. **Quieren un `temperature`.** No hace falta; el original lo usaba (1.0 y 0.7) sin
   justificación. Si alguien quiere comparar, que lo haga en el Writer con `PLAN_CORTO`.

## Respuestas del quiz de apertura

1. **b** — controla qué variables ve el código, no qué puede hacer (`__builtins__`).
2. **b** — catálogo cerrado: acota el daño; el código como plan es más expresivo pero
   depende del prompt.
3. **b** — el executor es un router: despacha por nombre en `registro_agentes` y agrega el
   historial.
4. **b** — aisuite corre el loop de tool calling localmente y llama a tus funciones.
5. **b** — `(paso, agente, salida)`: índice 1 es el agente.

## Soluciones de la extensión opcional (esbozo)

- **Contar llamadas:**
  ```python
  CONTADOR = {"total": 0}
  _create_original = client.chat.completions.create
  def _create_contado(**kw):
      CONTADOR["total"] += 1
      return _create_original(**kw)
  client.chat.completions.create = _create_contado
  ```
  Con `PLAN_CORTO`: 3 ruteos + 3 agentes = 6 llamadas visibles; las vueltas de tools del
  Research van por dentro de aisuite (una sola `create` externa) y se cuentan con
  `tools usadas`. Buena discusión: "llamadas" no es lo mismo que "requests HTTP".
- **Cuarto agente:** `agente_verificador` extrae URLs del informe con
  `re.findall(r"https?://\S+", informe)` y busca cada una en las salidas de Research del
  historial (que viajan en la tarea enriquecida). Devuelve la lista de URLs no respaldadas.
  Hay que agregarlo al prompt del planner (como capacidad) y al de ruteo (como opción).
- **Ruteo por reglas:** acierta en planes bien escritos y falla en pasos mixtos ("buscar y
  resumir"). Conclusión esperada: el ruteo por LLM vale una llamada barata cuando los pasos
  los escribe otro LLM.
- **Historial acotado:** con las últimas dos salidas, el informe final pierde las URLs del
  primer Research si hubo dos pasos de búsqueda. Solución típica: pasar siempre todas las
  salidas de Research y solo las dos últimas del resto.
- **Plan en inglés:** mejora la pertinencia de arXiv. Las queries ya se piden en inglés en
  el system del Research, así que el efecto es menor que lo que los alumnos esperan.

## Rúbrica

Este lab era el **graded** del módulo original, pero no traía autograder ni criterios.
Propuesta de rúbrica (100 puntos). Los 55 primeros se verifican con `run_all` y lectura
de código; los 45 restantes requieren una corrida completa (la del profesor en vivo sirve
como referencia para comparar).

| # | Criterio | Pts | Cómo se verifica |
|---|---|---|---|
| 1 | `agente_planner` devuelve `list[str]` parseando JSON con `limpiar_json` + `json.loads`; levanta `ValueError` ante dict, lista vacía o elementos no-string | 15 | Tests `test_planner_*` (3) |
| 2 | `agente_research` pasa las tres funciones en `tools=`, `max_turns=6`, system prompt con los nombres reales de las tools y pedido de queries en inglés | 15 | Lectura de código + `tools usadas: N > 0` en la prueba rápida |
| 3 | `agente_writer` / `agente_editor`: system prompt acorde al rol, modelo correcto por default (barato / fuerte), devuelven `str` | 5 | Lectura de código |
| 4 | `agente_executor`: ruteo validado contra `registro_agentes` (ValueError si no existe), historial `list[tuple[str, str, str]]` del mismo largo que el plan | 10 | Tests `test_executor_rutea_*`, `test_executor_agente_desconocido_*`, `test_executor_json_roto_*` |
| 5 | El historial viaja como contexto: la tarea del paso N incluye las salidas de los pasos anteriores | 10 | Test `test_executor_pasa_el_historial_como_contexto` |
| 6 | Log legible por paso (número, agente, tarea recortada, tamaño de la salida) | 5 | Ver la salida de `PLAN_CORTO` |
| 7 | Corrida completa: el plan tiene 4–6 pasos atómicos y el último produce Markdown | 10 | Leer `pasos` |
| 8 | El informe final está en Markdown, tiene título, secciones y una lista de fuentes con URLs | 10 | Abrir `data/informe.md` |
| 9 | Las URLs del informe aparecen en alguna salida de Research del historial (no inventadas) | 10 | Chequeo manual o con el `agente_verificador` de la extensión |
| 10 | Costo: la corrida completa no supera 25 llamadas y el alumno puede explicar de dónde salen | 5 | Pregunta oral + `tools usadas` |
| 11 | Reflexión escrita (3–5 líneas): qué parte del pipeline evaluaría primero y con qué métrica | 5 | Texto en la última celda del notebook |

Umbral sugerido de aprobación: 60, con los criterios 1, 4 y 5 obligatorios.

## Diferencias con el lab original de DeepLearning.AI

El original es `graded/GL-M5.ipynb` ("Pattern for Highly Autonomous Agents — Planning
Workflows"). Venía resuelto, sin autograder y con varias inconsistencias.

- **Vaciado en 8 bloques sobre 5 funciones** (planner ×2, research ×2, writer, editor,
  executor ×2). Se agregó un ejemplo resuelto (`agente_resumidor`) porque el original no
  tenía ninguno.
- **`eval()` → `json.loads`.** El planner original hacía
  `eval(response.choices[0].message.content.strip())` con un comentario "evaluate only if
  the environment is safe". Ahora pide JSON, limpia fences con `utils.limpiar_json` y valida
  tipo y contenido.
- **Nombres reales de tools en el system prompt.** El original decía `arxiv_tool`,
  `tavily_tool`, `wikipedia_tool`; las funciones son `arxiv_search_tool`,
  `tavily_search_tool`, `wikipedia_search_tool`. Hay un test que fija que `tool_mapping` y
  los `__name__` coincidan.
- **`max_turns` 12 → 6** por costo, y se cuenta `tools usadas` desde `intermediate_messages`
  (la forma real de aisuite) para que el costo sea visible.
- **Modelos:** el original mezclaba `openai:o4-mini` (planner) y `openai:gpt-4o` (resto).
  Ahora `AI_STRONG` para planner y editor, `AI_CHEAP` para el resto, desde `.env`.
- **Sin `temperature`.** El original usaba 1.0 en planner y writer, 0.7 en editor, 0 en
  ruteo, sin explicar por qué.
- **Executor:** el original, ante un agente desconocido, agregaba al historial un string
  `"Unknown agent"` (con un emoji de advertencia) y seguía. Ahora levanta `ValueError` con los nombres válidos. También
  se imprimía un encabezado que decía "Editor Agent" para el executor (error de copia).
- **Research:** el original envolvía la llamada en `try/except Exception` y devolvía
  `"[Model Error: ...]"` como si fuera un resultado, escondiendo errores de API. Se quitó.
- **`research_tools`:** se usa la versión compartida de `comun/` (arXiv con la query
  codificada, Wikipedia vía API de MediaWiki sin el paquete `wikipedia`, Tavily con fallback
  si falta la key). La original dependía del paquete `wikipedia` y lanzaba excepción sin key.
- **Celda final:** el original hacía `executor_history[-1][-1].strip("`")` (que solo quita
  backticks en los extremos, no la línea ```markdown). Ahora `utils.quitar_fences` y
  `utils.guardar_informe` a `data/informe.md`.
- **Prompts en español**, con nota de que las queries van en inglés.
- **Quiz, workbook, guía con rúbrica y `tests.py` con `FakeClient`** son nuevos. El original
  decía "You'll be graded..." pero no incluía ningún criterio ni test.

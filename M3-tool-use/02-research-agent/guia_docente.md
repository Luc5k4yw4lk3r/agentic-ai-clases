# Guía docente — Agente de investigación con function calling "a mano"

## Ficha

| | |
|---|---|
| Duración | 3 h (sesión 2 del módulo, completa). |
| Prerrequisitos | Lab 01 de este módulo (tools con `aisuite`, lectura de trazas). M2 (reflexión en dos llamadas, validación de salidas). Python: dicts anidados, `json.loads`/`json.dumps`, `**kwargs`, `try/except`, `for` con `return` adentro. |
| Keys | `OPENAI_API_KEY` obligatoria. `TAVILY_API_KEY` opcional: sin ella `tavily_search_tool` cae a Wikipedia y lo avisa en el campo `source`. arXiv y Wikipedia no necesitan key pero sí internet. |
| Archivos | `lab.py` (fuente) → `notebook_alumno.ipynb` / `notebook_solucion.ipynb`; `research_tools.py` (copia de `comun/`, compartida con M4 y M5); `utils.py`; `tests.py` (`run_all` desde el notebook o `pytest -q` para el docente); `workbook.md`. Genera `informes/<slug>.html` al correr el pipeline. |
| Modelos | `MODEL_CHEAP` para el loop de tools y el HTML; `MODEL_STRONG` para crítica y reescritura. |
| Costo estimado | **Cada corrida completa del pipeline son entre 5 y 10 llamadas**: 2 a 6 del loop (una por turno), 2 de reflexión (modelo fuerte, con el informe entero en el prompt) y 1 de HTML. Las celdas de demo (2.1 y 2.2) suman 2 más; la sección 5 y las pruebas individuales de 6 y 7, otras 4 a 8. Un alumno que sigue el notebook sin repetir gasta unas 15 a 25 llamadas; con la extensión 1 y 3, el doble. Con 20 alumnos conviene avisar que el pipeline de la sección 8 se corre **una vez**. |
| Se evalúa | Sí (era el graded lab del original). Rúbrica abajo. `tests.py` cubre lo estructural sin API; la calidad del informe se mira a mano. |

## Secuencia sugerida (sesión 2, 3 h)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–10 | Quiz de apertura. Las preguntas 1 y 2 repasan ayer; la 3 y la 4 son el núcleo de hoy: decirlo explícitamente. | Todos |
| 10–30 | Teoría (workbook §1.1–1.3): los cuatro pasos del protocolo en el pizarrón. Preguntar "¿cuáles de estos hizo aisuite ayer?" (todos). Mostrar `arxiv_tool_def` y compararlo con el docstring de la función: es lo mismo que ayer generaba `mostrar_schema`. | Profesor |
| 30–50 | Notebook secciones 1, 2, 2.1 y 2.2 **en vivo**, con los alumnos siguiendo. Detenerse en `content=None` y en las comillas de `arguments`. Son las dos celdas resueltas que después generalizan. | Profesor, alumnos siguen |
| 50–65 | Hueco 1: `wikipedia_tool_def`. Chequear con `comparar_schemas` y `run_all`. Recorrer y mirar las `description` que escribieron: ¿dicen cuándo usarla? | Alumnos |
| 65–75 | Sección 4 (despacho). Breve: el `assert` que cruza schemas con `tool_mapping`. | Alumnos |
| 75–105 | Huecos 2, 3 y 4: el loop. Es el centro de la sesión; dar tiempo. Insistir: `run_all(investigar_con_tools)` **antes** de la celda real. El test de la tool que falla suele ser el que queda rojo. | Alumnos, el profesor recorre |
| 105–115 | Pausa. | |
| 115–130 | Corrida real de la sección 5. Leer la traza impresa: cuántos turnos, qué queries eligió (¿en inglés?). Comparar entre alumnos: distintas secuencias para el mismo pedido. | Alumnos corren, discusión |
| 130–150 | Hueco 5 (`reflexionar_y_reescribir`). Conectar con M2. Mostrar en la celda de prueba por qué `critica != informe_revisado` es un chequeo: contar lo que hacía el original. | Alumnos |
| 150–160 | Hueco 6 (`convertir_a_html`). Rápido; el punto es `quitar_fences` y la validación. | Alumnos |
| 160–175 | Sección 8: pipeline completo, **una vez por alumno**, cada uno con un tema distinto si quieren. Abrir el HTML en el navegador. Comparar el contador de llamadas entre alumnos con la estimación que hicieron antes. | Alumnos |
| 175–180 | Cierre: las tres preguntas del workbook §5. Entregable: el notebook con los 6 huecos y el HTML generado. Anticipar M4: evaluar si el informe es bueno sin leerlo uno mismo. | Profesor |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

**En vivo (profesor, pantalla compartida):**

- Las celdas 2.1 y 2.2. Son el modelo mental del lab; conviene que las vean
  antes de escribir el loop, con los prints comentados uno por uno.
- Un `BadRequestError` provocado a propósito: quitar el `messages.append(msg)`
  del paso 1 y mostrar el error 400 de la API. Es el error que más van a ver y
  el mensaje es críptico.
- La lectura de una traza real de la sección 5.

**Los alumnos corren solos:**

- Los seis huecos, cada uno con su `run_all` antes de tocar la API.
- La sección 5 real (una vez), 6 y 7 reales (una vez cada una), el pipeline de
  la 8 (una vez).
- Extensión opcional en casa.

**Control de costo:** pedir que cada función se pruebe primero con `run_all`
(cliente falso, cero llamadas). Si alguien corre la sección 8 en loop para
"probar temas", son 10 llamadas por vuelta con el modelo fuerte.

## Dónde se traban (y qué decir)

1. **"¿Por qué escribir a mano lo que aisuite ya hacía?"** Porque es el
   protocolo real: cualquier framework (LangChain, el Agents SDK, lo que venga)
   hace esto adentro. Cuando falla, hay que saber leer el `tool_call`. Y porque
   mañana pueden necesitar un proveedor que aisuite no soporte.
2. **`arguments` es un string.** Igual que ayer, pero hoy les pega de frente:
   `funcion(**call.function.arguments)` da `TypeError`. Mostrar `repr()` de
   `arguments` y las comillas.
3. **El mensaje del modelo tiene que ir antes que los `tool`.** El error de la
   API dice algo como `messages with role 'tool' must be a response to a
   preceding message with 'tool_calls'`. Traducir: "la API quiere ver pedí → acá
   está, en ese orden". Es el paso 1 del hueco: `messages.append(msg)`.
4. **`tool_call_id`.** Algunos ponen el nombre de la tool o inventan un string.
   Tiene que ser `call.id`. El test `check_loop_ejecuta_tool_y_agrega_mensaje_tool`
   lo detecta antes de gastar una llamada.
5. **El `try/except` del paso 3.** Les parece opcional. Provocarlo: desconectar
   la red y correr; sin el `except`, el loop muere con `ConnectionError` y se
   pierden los turnos anteriores. Con el `except`, el modelo recibe el error y
   escribe sin esa fuente (y lo dice).
6. **`required` con parámetros que tienen default.** Si ponen `max_results` en
   `required`, funciona pero el modelo manda siempre un valor. Es un aviso de
   `comparar_schemas`, no una falla; vale explicar la diferencia.
7. **"La reflexión funciona con una llamada."** Lo hacía el original y devolvía
   el mismo texto en las dos claves. Mostrar que `run_all` lo rechaza y
   preguntar: si la crítica y el informe revisado son el mismo texto, ¿qué
   acabás de medir?
8. **Fences en el HTML.** Ven la página con ```` ```html ```` arriba y creen que
   el modelo "se equivocó". Es el comportamiento normal; `quitar_fences` ya
   está escrita, solo hay que usarla y validar.
9. **Queries en español.** Si el modelo busca en arXiv en español, devuelve
   vacío y a veces reintenta hasta agotar turnos. El system prompt lo pide en
   inglés; si pasa igual, agregar al pedido "las queries en inglés".
10. **Red del aula.** arXiv (`export.arxiv.org`) y Wikipedia a veces están
    bloqueados en redes corporativas. Probar la celda de la sección 1 al
    principio de la clase, antes de que llegue el loop. Nota: en el entorno
    donde se generó este material la salida a arXiv y Wikipedia estaba
    bloqueada por proxy, así que las tools se validaron con respuestas
    simuladas; probarlas en la red del aula antes de la clase.

## Respuestas del quiz de apertura

1. **b**. `max_turns`. Sin él, aisuite hace una sola llamada y devuelve los `tool_calls` sin ejecutar (igual que el SDK directo).
2. **b**. Las tools disponibles definen las capacidades; sin `borrar_email` en la lista el modelo puede buscar pero no borrar.
3. **b**. `message.tool_calls` con nombre y argumentos (string JSON). Ejecutar es responsabilidad del código que llama.
4. **b**. `role: "tool"`, `tool_call_id` igual al `id` del `call`, y el resultado serializado en `content`. Sin eso, error 400.
5. **b**. Un dict de Python. De ahí sale el `**args`.

## Soluciones de la extensión opcional (esbozo)

1. **Sin Wikipedia.** Con gpt-4.1-mini el modelo suele compensar con
   `tavily_search_tool` (que sin key cae a Wikipedia igual, pero el modelo no
   lo sabe hasta ver el `source`) o escribe la definición desde su propio
   conocimiento sin cita. Buen disparador: "¿esa definición tiene fuente?".
2. **Traza completa.** Devolver `{"informe": msg.content, "messages": messages}`.
   La `mostrar_traza` recorre `messages`: si `getattr(m, "tool_calls", None)`
   imprime las llamadas; si `isinstance(m, dict) and m["role"] == "tool"`
   imprime `json.loads(m["content"])` resumido. Casi igual a la de ayer; la
   diferencia es que acá los dicts `tool` los armaron ellos.
3. **Crítica con criterios.**
   ```python
   r = client.chat.completions.create(model=model, messages=[...],
                                      response_format={"type": "json_object"})
   datos = json.loads(r.choices[0].message.content)
   for clave in ("fuentes", "precision", "claridad", "comentarios"):
       if clave not in datos:
           raise ValueError(f"La crítica no tiene la clave '{clave}': {datos}")
   ```
   Regla sugerida: si `fuentes < 3`, volver a `investigar_con_tools` con el
   pedido original más "Agregá al menos dos fuentes más y citá cada afirmación".
   Es el puente a M4 (evaluaciones).
4. **`fecha_de_hoy`.** Schema con `"parameters": {"type": "object", "properties": {}, "required": []}`.
   Con una description tipo "Devuelve la fecha de hoy" el modelo la llama casi
   siempre, haga falta o no; con "Devuelve la fecha de hoy. Usala SOLO si el
   pedido menciona fechas relativas (este mes, reciente)" la usa menos. Es la
   lección de ayer sobre docstrings, vista desde el schema.

## Rúbrica

| Criterio | Puntos | Logrado (puntaje completo) | Parcial | No logrado |
|---|---|---|---|---|
| Schema `wikipedia_tool_def` | 15 | Pasa `run_all`; description dice cuándo usarla; `required` correcto | Pasa pero description genérica ("busca en Wikipedia") o `required` incluye `max_results` | No pasa `run_all` o `name` no coincide |
| Loop `investigar_con_tools` | 35 | Pasa los 5 chequeos; traza impresa legible; la corrida real termina con informe citado | Pasa 3 o 4 (típicamente falla el de la tool rota o el de `max_turns`) | `BadRequestError` en la corrida real o loop que no corta |
| `reflexionar_y_reescribir` | 20 | Dos llamadas, la segunda recibe la crítica; valida vacíos; `MODEL_STRONG` por defecto | Dos llamadas pero sin validación, o la segunda no recibe la crítica | Una sola llamada / mismo texto en ambas claves |
| `convertir_a_html` | 10 | Quita fences, valida, el HTML se renderiza con enlaces clickeables | Renderiza pero quedaron fences o sin validación | No renderiza / `ValueError` sin motivo |
| Pipeline y costo | 10 | Corrió una vez; el HTML está en `informes/`; puede decir cuántas llamadas hizo y por qué | Corrió pero no sabe explicar el número de llamadas | No llegó al pipeline |
| Calidad del informe (lectura docente) | 10 | En español, con secciones, cada afirmación con URL real de las tools; sin "(cita pendiente)" | Fuentes presentes pero alguna no sale de las tools, o secciones sin cita | Sin fuentes o con fuentes inventadas |

Aprobado: 60 o más, con el loop (criterio 2) en al menos 25. El original no
tenía autograder ni rúbrica; `tests.py` cubre los criterios 1 a 4 en su parte
estructural, y el docente puede correr `pytest -q` sobre el `notebook_solucion`
de referencia o adaptar `_namespace_solucion` para leer el notebook entregado
por cada alumno (cambiar el nombre del archivo).

## Diferencias con el lab original de DeepLearning.AI

| Original (GL-M3) | Acá | Por qué |
|---|---|---|
| Modelos `gpt-4o` y `gpt-4o-mini` hardcodeados, con `temperature`. | `MODEL_CHEAP` / `MODEL_STRONG` del `.env`, por parámetro; sin `temperature`. | Convenciones del material; modelos retirados. |
| Las tres funciones venían resueltas (no había nada que completar aunque se llamaba "graded"). | Seis huecos graduados: schema → tres pasos del loop → reflexión → HTML. Celdas 2.1 y 2.2 resueltas como ejemplo previo. | Convertirlo en ejercicio real con gradualidad. |
| Sin ejemplo de "una vuelta a mano" antes del loop. | Secciones 2.1 y 2.2 muestran `tool_calls` crudos y una vuelta completa. | Es el mecanismo que aisuite escondía; verlo aislado antes de generalizar. |
| `reflection_and_rewrite` hacía una sola llamada y devolvía el mismo texto en `reflection` y `revised_report`. | Dos llamadas separadas; la segunda recibe la crítica; el test lo verifica. | El original no era reflexión; era un rename. |
| `convert_report_to_html` devolvía el texto crudo (con fences ```` ```html ````). | `quitar_fences` + validación con `ValueError`. | El HTML con fences se mostraba como texto. |
| `research_tools.py` propio: arXiv sin codificar la query (una query con guiones rompía la URL), Tavily sin fallback (lanzaba `ValueError` sin key), sin Wikipedia. | `comun/research_tools.py` compartido: query codificada, Tavily con fallback a Wikipedia avisado en `source`, Wikipedia vía MediaWiki con `requests`. | Bugs del original; el paquete `wikipedia` no está disponible; una sola copia para M3, M4 y M5. |
| `tool_mapping` solo con arXiv y Tavily; `wikipedia_tool_def` no existía. | Tres tools; el alumno escribe `wikipedia_tool_def`. | Hueco de schema a mano. |
| Sin manejo de `max_turns` agotado (devolvía `""`). | `RuntimeError` con mensaje en español. | Nada falla en silencio. |
| Prompts en inglés con emojis. | Prompts en español; queries en inglés con nota del porqué. | Los alumnos tienen que poder leer y modificar los prompts. |
| Sin tests ni rúbrica (el "graded" no tenía autograder). | `tests.py` con `FakeClient` (loop, `tool_call_id`, `max_turns`, tool rota, reflexión en dos llamadas, fences) + rúbrica. | Evaluable sin gastar API. |
| Tema de ejemplo: "Radio observations of recurrent novae". | RAG y agentes con tools. | Temas del propio curso; el alumno puede juzgar si el informe es razonable. |
| Sin quiz, workbook ni guía. | Agregados según convenciones. | |

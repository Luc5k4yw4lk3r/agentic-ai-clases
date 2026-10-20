# Guía docente — Evaluar un componente: ¿de dónde saca las fuentes el agente?

## Ficha

| | |
|---|---|
| **Duración** | 100 min (bloque 1 de la sesión de M4; el bloque 2 es la lectura de la app, lab 02) |
| **Prerrequisitos** | M3 completo (function calling, `aisuite` con tools, el agente de investigación). Saber qué es una URL y un dominio. Listas, `for`, `if`, f-strings. |
| **Keys** | `OPENAI_API_KEY` obligatoria. `TAVILY_API_KEY` opcional (sin ella las tools caen a Wikipedia y lo avisan). |
| **Archivos** | `lab.py` → `notebook_alumno.ipynb` / `notebook_solucion.ipynb`, `workbook.md`, `utils.py`, `tests.py`, `research_tools.py` (copia de `comun/`), `pytest.ini`. |
| **Costo estimado** | Por alumno: 1 llamada de prueba + 5 del gold standard = 6 llamadas a `MODEL_CHEAP` con tools (cada una 2 a 4 turnos). Con la extensión de 3 repeticiones, 15 más. Tools: arXiv y Wikipedia gratis; Tavily consume cuota. |
| **Se evalúa** | Sí: `pytest -q` (24 tests sin API) + la tabla del gold standard. Rúbrica abajo. |

## Secuencia sugerida (100 min)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–10 | Quiz de apertura en el chat. Corregir en voz alta la 5 (`in` es substring): es el gancho del lab. | Profesor |
| 10–25 | Teoría: los dos ejes de evaluación (tabla del workbook) y por qué empezar por el cuadrante objetivo + ground truth. Mostrar el pipeline de M3 y marcar dónde se corta. | Profesor |
| 25–35 | Celda de setup + `buscar_referencias` en vivo. Mientras corre (30-60 s), explicar `max_turns` y la fecha en el prompt. | Profesor en vivo |
| 35–45 | Celda "ejemplo resuelto": `re.findall`, `urlparse`, y la demo del bug `"mit.edu" in "summit.edu"`. Pedirles que predigan el resultado antes de ejecutar. | Profesor + alumnos |
| 45–70 | Huecos 3.1 a 3.4 (funciones puras). `run_all` como semáforo. Circular por el aula. | Alumnos |
| 70–75 | Puesta en común: cuántos pasaron 24/24, qué test falló más. | Todos |
| 75–90 | Hueco 3.5 (`correr_evaluacion`) y correrlo. Lectura de la tabla en grupo. | Alumnos |
| 90–100 | Cierre: las tres preguntas de reflexión. Puente al lab 02 ("ahora vamos a ver dónde vive este agente en una app real"). | Profesor |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

- **En vivo (profesor):** setup, `buscar_referencias` de prueba, celda de ejemplo resuelto. Son
  las celdas que más contexto necesitan y las que consumen tiempo de espera.
- **Alumnos solos:** los cinco huecos. Los cuatro primeros se validan con `run_all` sin gastar
  API. El quinto llama al modelo cinco veces: avisarles que tarda 1 a 2 minutos y que no
  reejecuten la celda "para ver si cambia" (sí cambia, y cuesta).
- **Si la red o la API fallan:** las secciones 3.1 a 3.4 y los tests funcionan sin conexión. Se
  puede hacer casi toda la clase offline y dejar `correr_evaluacion` para la casa.

## Dónde se traban (y qué decir)

1. **`set` para deduplicar** (3.1). Muchos escriben `list(set(urls))` y el test de orden falla.
   Decir: "un set no recuerda el orden; usá una lista y preguntá `if url not in urls`".
2. **`endswith(confiable)` sin el punto** (3.3). Parece arreglar el bug pero no:
   `"summit.edu".endswith("mit.edu")` → `True`. El test
   `test_confiable_no_confunde_substring` lo atrapa. El punto antes del dominio es la clave:
   `"summit.edu".endswith(".mit.edu")` → `False`, `"web.mit.edu".endswith(".mit.edu")` → `True`.
3. **División por cero** (3.4). El test `sin_urls` lo atrapa. Decir que un texto sin URLs es un
   caso real: el modelo puede devolver `[Error ...]` o un texto sin links.
4. **`aprobado` con umbral 0** (3.4). Si ponen solo `ratio >= umbral`, un texto vacío aprueba
   con umbral 0. Hay un test para eso. Preguntar: "¿tiene sentido que un agente que no cita
   nada apruebe?".
5. **Olvidan reejecutar la celda de la función antes de `run_all`** (muy común en Jupyter). Si
   `run_all` sigue diciendo `FALTA`, es eso.
6. **Las referencias no son recientes** aunque el prompt pida "recent". Es el momento de
   explicar por qué la fecha va en el prompt y de mostrar que sin ella el modelo "vive" en su
   fecha de entrenamiento.
7. **El gold standard les parece arbitrario** ("¿por qué `wikipedia.org` es confiable?"). Es
   una discusión que vale tener 3 minutos: el ground truth lo define el equipo, y definirlo es
   trabajo. No hay lista correcta universal.

## Respuestas del quiz de apertura

1. **b**. El modelo devuelve nombre y argumentos; el código ejecuta la función y le devuelve el
   resultado como mensaje `tool`.
2. **b**. Cada turno es una llamada al modelo que puede pedir tools; `aisuite` corta en 5 y
   devuelve lo que haya.
3. **b**. Es la tesis del lab: señal más limpia y más barata.
4. **b**. Hay una regla objetiva (sufijo de dominio) y una lista definida por tema.
5. **b**. Y por eso el original tenía falsos positivos.

## Soluciones de la extensión opcional (esbozo)

1. **Varianza.**
   ```python
   df3 = correr_evaluacion(CASOS, repeticiones=3)
   resumen = df3.groupby("tema")[["ratio", "aprobado"]].agg(["mean", "std"])
   ```
   Lo esperable: 1 o 2 temas con `aprobado` promedio entre 0.33 y 0.67 (cambian de PASS a
   FAIL). La lección: una corrida no alcanza; reportar media y desvío, o usar "aprueba si pasa
   en ≥ 2 de 3".
2. **Umbral.** `for u in (0.3, 0.5, 0.7): print(u, (df["ratio"] >= u).sum())`. No hay umbral
   correcto: depende de cuánto cuesta un falso FAIL (revisar a mano) vs. un falso PASS.
3. **Tema nuevo.** Cualquiera sirve. Lo que importa es que anoten la dificultad de armar la
   lista. Si eligen un tema no científico ("historia del tango"), van a ver que las tools
   (arXiv) no ayudan y que el ground truth cambia por completo.
4. **Cambiar el prompt.** Agregar "Priorizá fuentes académicas e institucionales (.edu, .gov,
   arxiv)" suele subir el ratio. Lo central es que lo midan con `correr_evaluacion` antes y
   después, no que lo "vean".
5. **Paréntesis.** Regex que permita `)` y después recortar: si la URL candidata tiene más `)`
   que `(`, sacar los `)` sobrantes del final:
   ```python
   while url.endswith(")") and url.count(")") > url.count("("):
       url = url[:-1]
   ```
   Con la regex `r"https?://[^\s<>\"'\]]+"` (sin excluir `)`), `[paper](https://arxiv.org/x)`
   da `https://arxiv.org/x)` → se recorta a `https://arxiv.org/x`; y
   `.../Transformer_(deep_learning_architecture)` queda entero.

## Rúbrica

| Criterio | Puntos |
|---|---|
| `pytest -q` verde (24/24) | 50 |
| `correr_evaluacion` devuelve el DataFrame con las 6 columnas y corre sobre los 5 casos | 20 |
| Puede explicar oralmente el bug del substring y por qué el `.` lo arregla | 15 |
| Extensión: al menos una de las cinco con resultado y una frase de conclusión | 15 |

## Diferencias con el lab original de DeepLearning.AI

| Original (M4_UGL_1) | Acá | Por qué |
|---|---|---|
| Todo resuelto; el único ejercicio era cambiar `topic` y `min_ratio` | 5 funciones con 10 huecos graduados + tests | Convertirlo en práctica, no en lectura |
| `any(td in domain for td in TOP_DOMAINS)` | Igualdad o `endswith("." + d)` | `in` es substring: `summit.edu` pasaba por `mit.edu`. El workbook lo convierte en ejercicio |
| URLs duplicadas contaban dos veces | Dedup conservando orden | El total inflaba el ratio |
| `url.split("/")[2]` para el dominio | `urlparse(...).netloc` sin `www.` | `split` rompe con URLs sin path y no normaliza `www.` |
| Puntuación pegada a la URL | `rstrip(".,;:!?")` | Links rotos en el detalle |
| Un solo tema (agujeros negros) | Gold standard de 5 temas con dominios por tema + `correr_evaluacion` con repeticiones | Mostrar que el ground truth depende del tema y que una corrida no alcanza |
| `print_html` escapaba el HTML (las etiquetas aparecían como texto) | `utils.mostrar_html` no escapa; `mostrar_texto` sí | Bug visual del original |
| `utils.py` original con tres versiones de `evaluate_tavily_results` (dos sobreescritas) y helpers no usados (`duckdb`, `evaluate_references` sobre un `history`) | `utils.py` mínimo, solo visualización | Código muerto confunde a alumnos junior |
| `model="openai:gpt-4o"` hardcodeado | `AI_CHEAP` desde `.env` | Convención del material; `gpt-4o` está retirado |
| `research_tools.py` con `import wikipedia` y arXiv sin `quote` de la query | `comun/research_tools.py` (requests + MediaWiki, `urllib.parse.quote`) | El paquete `wikipedia` no está; la query sin codificar rompía con guiones |
| Prompt en inglés | Prompt en español, queries a tools en inglés con nota | Los alumnos tienen que poder leer y modificar el prompt |
| Sin tests | `tests.py` con 24 casos borde + `run_all` | Semáforo inmediato sin gastar API |

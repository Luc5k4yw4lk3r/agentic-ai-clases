# M2 — Reflexión

Primer patrón agéntico del curso. Un LLM genera algo, **mira el resultado** (su propio
texto, una tabla, una imagen) y lo corrige. Los tres labs usan el mismo mecanismo con
tres tipos de feedback cada vez más externos al modelo.

## Objetivo del módulo

Al terminar, el alumno puede:

- Encadenar llamadas a un LLM donde la salida de una es la entrada de la siguiente.
- Explicar la diferencia entre reflexión "en papel" (el modelo relee su salida) y
  reflexión con **feedback externo** (ejecutar la salida y mostrarle el resultado).
- Pedir respuestas estructuradas (JSON, código entre etiquetas) y **validarlas**
  explícitamente, sin fallbacks silenciosos.
- Armar un mensaje multimodal (texto + imagen) con el SDK de OpenAI.
- Juzgar qué puede y qué no puede detectar un crítico según qué información recibe.

## Labs en orden

| # | Lab | Feedback que ve el crítico | Cliente | Huecos | Evaluado |
|---|---|---|---|---|---|
| 01 | [`01-ensayo-reflexion`](01-ensayo-reflexion/) — borrador → crítica → revisión de un ensayo, más un bucle de N rondas | el texto que él mismo escribió | aisuite | 7 | Sí (tests sin API + rúbrica) |
| 02 | [`02-sql-reflexion`](02-sql-reflexion/) — pregunta en castellano → SQL → ejecutar → corregir | la tabla que devolvió la base | aisuite | 10 | No |
| 03 | [`03-graficos-reflexion`](03-graficos-reflexion/) — instrucción → código matplotlib → PNG → crítica con visión → V2 | la imagen que generó su código | SDK openai | 7 | No |

El orden va de mecanismo simple a complejo: en 01 lo único nuevo es encadenar llamadas;
en 02 se agrega ejecutar la salida y parsear JSON; en 03 se agregan `exec` controlado,
regex sobre etiquetas y mensajes con imagen.

Cada carpeta tiene `notebook_alumno.ipynb` (lo que se corre en clase), `workbook.md`
(teoría breve, ejemplo resuelto, práctica graduada, troubleshooting), `guia_docente.md`
(secuencia minuto a minuto, dónde se traban, respuestas del quiz, diferencias con el
original) y `utils.py`. El 01 tiene además `tests.py`. Los notebooks se generan desde
`lab.py` con `python3 tools/build_nb.py <ruta/lab.py>`; no se editan a mano.

## Reparto en sesiones de 3 h

### Sesión 1 — Reflexión: el patrón y el feedback externo (180 min)

| Minuto | Bloque |
|---|---|
| 0–10 | Apertura: qué es un patrón agéntico; por qué un LLM que "piensa de una" se equivoca de formas que él mismo detectaría. Un ejemplo humano (corregir un mail). |
| 10–25 | Teoría de reflexión: el flujo generar → criticar → revisar; por qué en llamadas separadas; qué cambia cuando el artefacto es ejecutable. Anticipar los tres labs como tres tipos de feedback. |
| 25–85 | **Lab 01** (60 min). Secuencia en su guía docente. Termina con `run_all` 4/4. |
| 85–95 | Pausa. |
| 95–170 | **Lab 02** (75 min). Secuencia en su guía docente. Arranca con el modelo de eventos en el pizarrón. |
| 170–180 | Cierre: tabla comparativa "qué vio el crítico / qué atrapó" para 01 y 02. Pregunta para la próxima: "¿y si lo que genera el modelo es una imagen?". Tarea: extensión opcional del lab 01 (crítico y escritor con modelos distintos) o del 02 (documentar la convención). |

Si el grupo es lento, cortar el lab 02 en `refinar_sql_con_feedback` (hueco 7) y dejar
el workflow como tarea: lo esencial es haber visto la diferencia entre la variante en
papel y la variante con feedback.

### Sesión 2 — Reflexión multimodal y límites del patrón (180 min)

| Minuto | Bloque |
|---|---|
| 0–15 | Repaso con el quiz del lab 03 (sus dos primeras preguntas repasan la sesión 1). Revisar la tarea: ¿qué pasó con modelos distintos por rol? |
| 15–105 | **Lab 03** (90 min). Secuencia en su guía docente. Incluye la "apuesta" sobre el Q1 2024 y la extensión 1 como cierre. |
| 105–115 | Pausa. |
| 115–135 | Límites de la reflexión (20 min, discusión guiada): el crítico ve lo que le mostrás; rendimientos decrecientes de más rondas; el crítico es condescendiente con su propio texto; costo (cada ronda duplica o triplica las llamadas); cuándo conviene documentar mejor la entrada en vez de reflexionar. Usar las tres preguntas "Para cerrar" de cada workbook. |
| 135–175 | **Proyecto corto en parejas** (40 min): elegir uno de los tres labs y agregarle **una** mejora de la extensión opcional (condición de corte, reflexión sobre el error, rúbrica numérica, darle los datos al crítico). Al final, cada pareja muestra en 2 minutos qué cambió y qué observó. |
| 175–180 | Cierre del módulo. Puente a M3: en estos labs el modelo recibía el resultado de ejecutar su salida porque nosotros lo ejecutábamos; en M3 el modelo va a pedir él mismo ejecutar cosas (tools). |

## Prerrequisitos

- Entorno listo: `python setup/check_env.py` sin FALTA. Python 3.11+.
- `.env` en la raíz del material con `OPENAI_API_KEY`, `MODEL_CHEAP` y `MODEL_STRONG`
  (ver `.env.example`). Este módulo **no** usa Tavily.
- Python básico: funciones con parámetros por defecto, f-strings, listas y
  diccionarios, `try/except`. SQL básico para el lab 02 (`SELECT`, `WHERE`,
  `GROUP BY`, `SUM`).
- Haber hecho al menos una llamada a un LLM por API. Si no, la celda resuelta
  `preguntar` del lab 01 lo cubre en vivo.

## Qué se evalúa

- **Lab 01** es el evaluado del módulo. `tests.py` tiene 4 chequeos estructurales sin
  API (usan un cliente falso que registra los prompts: verifican que `revisar_borrador`
  reciba la crítica, que `model` no esté hardcodeado y que el bucle encadene sobre la
  última versión) y 1 de integración con API. Rúbrica de 10 puntos en su guía docente;
  aprobado con 6.
- **Labs 02 y 03** no llevan nota. Entregable sugerido: el notebook corrido con las
  preguntas/instrucciones extra y una celda markdown con una conclusión de dos o tres
  oraciones (qué criticó el modelo, qué corrigió, qué no vio).
- **Proyecto corto** de la sesión 2: participación, no nota.

## Costo estimado por alumno

Lab 01: ~12 llamadas a `MODEL_STRONG` (ensayos de 300–400 palabras). Lab 02: ~10
llamadas cortas. Lab 03: ~4 llamadas, dos con imagen. Total del módulo por alumno:
**~26 llamadas**; para un grupo de 20, unas 520 más lo que repitan en extensiones.

## Datos

- `02-sql-reflexion/data/productos.db`: se genera con `utils.crear_db_transacciones`
  (seed 42, 100 productos, 5.000 eventos). Se regenera al correr el setup del notebook.
- `03-graficos-reflexion/data/coffee_sales.csv`: copiado del material original
  (3.636 ventas, 2024-03-01 a 2025-03-23). Los PNG que genera el lab van a la misma
  carpeta y se borran al inicio de cada corrida.

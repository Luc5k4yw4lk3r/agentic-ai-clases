# M4 — Evaluación y la app de referencia

## Objetivo del módulo

Hasta M3 los alumnos construyeron agentes: reflexión (M2), tools y function calling (M3). En
M4 dan un paso atrás y se preguntan **cómo saber si un agente funciona** y **cómo se ve un
agente dentro de una aplicación real**. Dos ideas:

1. **Evaluar por componente.** En vez de correr todo el pipeline y leer el reporte final,
   medir un paso aislado con una métrica objetiva calculada por código, con un ground truth
   definido por ejemplo. Es barato, reproducible y detecta regresiones.
2. **Leer código de producción.** La app pública de DeepLearning.AI integra planner, agentes
   especializados, tools, persistencia y UI. Leerla con una guía, encontrarle los bugs y
   extenderla enseña más que escribirla de cero.

Al terminar el módulo el alumno puede: diseñar una evaluación objetiva para un paso de un
agente, armar un gold standard chico y leer sus resultados; seguir una request por una app
FastAPI con agentes en un thread; reconocer los patrones del curso en código ajeno; y
proponer un arreglo a partir de un síntoma.

## Labs en orden

| Lab | Qué se hace | Formato | Tiempo |
|---|---|---|---|
| `01-evaluar-busqueda/` | Evaluación a nivel de componente del paso de búsqueda: `extraer_urls`, `dominio_de`, `es_dominio_confiable`, `evaluar_referencias`, `correr_evaluacion` sobre un gold standard de 5 temas. Corrige tres bugs del original (substring, duplicados, puntuación) y los convierte en ejercicios. | Notebook (10 huecos) + workbook + tests (24, sin API) | ~100 min |
| `02-app-research-agent/` | Lectura guiada de la app FastAPI (planner → executor → agentes → tools → DB → UI por polling), caza de 4 bugs, 3 ejercicios de código (integrar la evaluación del lab 01, reintentos del writer, modelo por request) y 1 de diseño (ruteo con LLM). | `guia_lectura.md` + `ejercicios.md` + `guia_docente.md` + `app/` corriendo | ~70 min (lectura + caza de bugs); +80 min con los ejercicios de código |

El lab 02 no tiene notebook: el "cuaderno" es la app misma, con `uvicorn --reload` al lado del
editor.

## Reparto en sesiones de 3 h

### Opción recomendada: una sesión

| Bloque | Minutos | Contenido |
|---|---|---|
| 1 | 0–100 | Lab 01 completo: quiz, teoría (dos ejes de evaluación), `buscar_referencias` en vivo, 5 huecos con `run_all` como semáforo, gold standard de 5 temas, cierre. |
| Pausa | 100–110 | |
| 2 | 110–180 | Lab 02: quiz, corrida proyectada de la app, lectura guiada §0 a §7, caza de bugs A1 a A4 en grupos, puesta en común de A1 y A2. Las partes B y C van de tarea. |

**Por qué así.** Los dos labs son una sola idea contada dos veces: en el 01 se construye la
evaluación en aislamiento; en el 02 se ve dónde falta dentro de un sistema real (ejercicio B1
es exactamente "poné lo del 01 acá"). Separarlos en dos sesiones pierde ese puente. Además el
lab 02 en su núcleo (lectura + caza de bugs) no gasta API y no depende de que los alumnos
tipeen rápido, así que cabe en 70 minutos aunque el grupo venga lento del bloque 1.

### Opción alternativa: dos sesiones

Si el grupo tiene poca base de Python o se quiere hacer la parte B en clase (vale la pena si el
bootcamp sigue con un módulo de backend):

- **Sesión A:** lab 01 (100 min) + lectura §0 a §3 de la app (50 min) + A1 y A2 (30 min).
- **Sesión B:** lectura §4 a §8 (30 min) + A3, A4 (20 min) + B1 (60 min) + B2 o B3 (45 min) +
  C1 en papel y cierre (25 min).

El detalle minuto a minuto de cada variante está en la guía docente de cada lab.

## Prerrequisitos

- M3 completo: function calling con el SDK de OpenAI, `aisuite` con tools y `max_turns`, el
  agente de investigación con arXiv/Tavily/Wikipedia, y el servidor FastAPI del email
  assistant (para que `main.py` del lab 02 no sea la primera vez que ven un endpoint).
- Python: listas, `for`/`if`, f-strings, `dict`, importar un módulo propio. El lab 01 enseña
  `re.findall`, `urlparse` y `endswith` con una celda de ejemplo resuelto.
- `.env` en la raíz del material con `OPENAI_API_KEY`, `MODEL_CHEAP`, `MODEL_STRONG`.
  `TAVILY_API_KEY` opcional (las tools caen a Wikipedia y lo avisan). Para el lab 02, además,
  `app/.env` (copiar `app/.env.example`; con sqlite no hace falta Docker ni Postgres).
- Red: arXiv y Wikipedia (sin key). Ver "Riesgos de correrla en clase" en la guía docente del
  lab 02 antes de la sesión (límites de arXiv por IP, créditos de Tavily, CORS abierto).

## Qué se evalúa

| Lab | Instrumento | Peso sugerido |
|---|---|---|
| 01 | `pytest -q` en la carpeta (24 tests, sin API) + `correr_evaluacion` sobre los 5 casos + explicación oral del bug del substring + una extensión | 50 % |
| 02 | Entrega escrita de la caza de bugs (A1 a A4: línea, causa, arreglo) + un ejercicio B que corra (con agentes falsos o con API) + C1 en papel | 50 % |

Rúbricas detalladas en `01-evaluar-busqueda/guia_docente.md` y
`02-app-research-agent/guia_docente.md`.

## Costo estimado en llamadas

| | Por alumno | Por grupo de 25 |
|---|---|---|
| Lab 01, nivel base | 6 llamadas a `MODEL_CHEAP` con tools (1 prueba + 5 del gold standard) | ~150 |
| Lab 01, extensión de 3 repeticiones | +15 | +375 |
| Lab 02, corrida completa de la app | 8 a 12 llamadas (1 a `MODEL_STRONG`, el resto `MODEL_CHEAP`; el writer hasta 15 000 tokens de salida) | 1 proyectada + 1 por grupo de 3-4 → ~80 |

Recomendación: en el lab 02, una corrida por grupo, no por alumno; y `ARXIV_FETCH_PDF=0` en el
`.env` de la app para que el paso de research no descargue PDFs.

## Archivos comunes

`01-evaluar-busqueda/research_tools.py` es una copia tal cual de `comun/research_tools.py`
(arXiv, Wikipedia vía MediaWiki, Tavily con fallback). La app del lab 02 tiene su propia
versión en `app/src/research_tools.py` con la misma lógica de Wikipedia y Tavily más la
descarga opcional de PDFs de arXiv que traía el original.

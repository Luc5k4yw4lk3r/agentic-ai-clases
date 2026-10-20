# M3 — Tool use

## Objetivo del módulo

Que el alumno pase de "el modelo genera texto" a "el modelo decide qué funciones
ejecutar". Al terminar puede:

- envolver una API REST en funciones Python que un LLM puede pedir que se ejecuten (tools),
  y explicar por qué el docstring y la firma son lo único que el modelo ve;
- lanzar el loop de tool use con `aisuite` (`tools=[...]`, `max_turns`) y leer la traza;
- escribir ese mismo loop a mano con el SDK de OpenAI: schema JSON, `tool_calls`,
  mensaje `tool` con `tool_call_id`, condición de corte;
- encadenar tools → reflexión → formato en un pipeline y estimar lo que cuesta.

La idea central, repetida en los dos labs: **las tools disponibles definen lo que el
agente puede hacer**, y el modelo nunca ejecuta nada, solo pide.

## Contenido

```
M3-tool-use/
  README.md               # este archivo
  email_server/           # API REST simulada (FastAPI + SQLAlchemy + SQLite), con tests
  01-email-assistant/     # lab 01: tools con aisuite sobre el servidor de email
  02-research-agent/      # lab 02: function calling a mano, agente de investigación
```

### `email_server/`

Reconstrucción del servidor que el material original usaba pero no incluía. Diez
endpoints, el mismo patrón que TaskFlow (`database.py`, `models.py`, `schemas.py`,
`main.py`), semilla de 6 mails en español. Se levanta desde `M3-tool-use/`:

```bash
uvicorn email_server.main:app --reload --port 8000
```

Detalles y pruebas en `email_server/README.md`.

### Lab 01 — Asistente de email con tools (aisuite)

Tools como funciones Python; `aisuite` arma los schemas y corre el loop. El alumno
escribe dos tools, el prompt del agente, la función que lee la traza y la llamada
con `max_turns`. Experimento central: el mismo pedido de borrado sin y con la tool
`borrar_email`. Ungraded. 8 huecos.

### Lab 02 — Agente de investigación con function calling a mano

SDK de OpenAI directo. El alumno escribe un schema JSON, el loop completo (tres
pasos), la reflexión en dos llamadas y la conversión a HTML. Tools de arXiv,
Wikipedia y Tavily (con fallback). Evaluable, con `tests.py` sin API y rúbrica.
8 huecos.

## Reparto en sesiones de 3 h

### Sesión 1 — Servidor + lab 01

| Bloque | Minutos | En vivo (profesor) | Corren los alumnos |
|---|---|---|---|
| Quiz | 10 | Comentar respuestas | |
| Servidor de email | 35 | Levantarlo, recorrer `/docs`, mostrar `main.py` y la tabla "TaskFlow / acá" | Levantarlo cada uno y verificar en `/docs` |
| Teoría: tools, loop, schema | 15 | Diagrama en el pizarrón; `mostrar_schema` línea por línea | |
| Lab 01 secciones 1–3 | 35 | Recorrer | Verificar servidor, tools a mano, huecos 1 y 2 |
| Pausa | 10 | | |
| Lab 01 secciones 4–6 | 35 | Leer una traza real en voz alta | Huecos 3, 4 y 5; primera corrida real |
| Experimento (sección 7) y pedido ambiguo (8) | 25 | Corrida 7.1 compartida; discusión sobre alucinación de acción | 7.2 y 8 |
| Cierre | 15 | Preguntas del workbook; dejar extensión como tarea | |

Minuto a minuto en `01-email-assistant/guia_docente.md`.

### Sesión 2 — Lab 02

| Bloque | Minutos | En vivo (profesor) | Corren los alumnos |
|---|---|---|---|
| Quiz | 10 | Comentar; marcar que 3 y 4 son el núcleo de hoy | |
| Teoría: los cuatro pasos del protocolo | 20 | Pizarrón; comparar `arxiv_tool_def` con el docstring de ayer | |
| Secciones 1, 2, 2.1, 2.2 | 20 | Celdas resueltas, con los prints comentados | Seguir y ejecutar |
| Hueco 1 (schema) y sección 4 | 25 | Recorrer; mirar las descriptions | `wikipedia_tool_def`, despacho |
| Huecos 2–4 (el loop) | 30 | Provocar el error 400 de la API a propósito | Loop con `run_all` antes de la API |
| Pausa | 10 | | |
| Corrida real (sección 5) | 15 | Leer una traza | Correr una vez, comparar secuencias |
| Huecos 5 y 6 | 30 | Conectar con M2 | Reflexión, HTML, con `run_all` primero |
| Pipeline (sección 8) | 15 | Comparar contador de llamadas con la estimación | Una corrida por alumno; abrir el HTML |
| Cierre | 5 | Entregable y anticipo de M4 | |

Minuto a minuto en `02-research-agent/guia_docente.md`.

## Prerrequisitos

- M2 completo: llamadas con `aisuite`, patrón de reflexión, validación de salidas.
- TaskFlow (módulo de FastAPI): saber qué es un endpoint, haber usado `/docs`,
  entender que el frontend llamaba a la API con `fetch`.
- Python: funciones con type hints, dicts y listas, `for` con `if`, f-strings,
  `json.loads`/`json.dumps`, `try/except`, `**kwargs`.
- Entorno: `requirements.txt` de la raíz instalado, `.env` con `OPENAI_API_KEY`,
  `MODEL_CHEAP`, `MODEL_STRONG` y `M3_EMAIL_SERVER_API_URL`. `TAVILY_API_KEY`
  opcional. Chequear con `python setup/check_env.py`.
- Internet en el aula hacia `export.arxiv.org` y `en.wikipedia.org` (lab 02).
  Probar antes de la clase; algunas redes corporativas los bloquean.

## Qué se evalúa

- **Lab 01**: no se califica. Rúbrica orientativa en su guía docente.
- **Lab 02**: sí. Entregable: `notebook_alumno.ipynb` con los 6 huecos completos y
  el HTML generado en `informes/`. `tests.py` verifica la parte estructural sin API
  (`run_all` desde el notebook o `pytest -q`); la calidad del informe se lee a
  mano. Rúbrica de 100 puntos en `02-research-agent/guia_docente.md`, aprobado con
  60 y el loop en al menos 25.

## Costo

Lab 01: unas 15 a 25 llamadas cortas por alumno a `MODEL_CHEAP`. Lab 02: cada
corrida completa del pipeline son 5 a 10 llamadas, la mitad a `MODEL_STRONG` con
el informe entero en el prompt; un alumno que sigue el notebook sin repetir hace
15 a 25 llamadas. Las dos guías docentes tienen el desglose y cómo contenerlo
(probar cada función con `run_all` o `respuesta_simulada()` antes de la API).

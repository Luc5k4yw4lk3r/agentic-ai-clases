# M5 — Multi-agente

Último módulo del material. Hasta acá cada lab tenía **un** agente que planificaba, usaba
tools y escribía. En M5 el trabajo se reparte entre varios roles que se pasan información:
un planner que propone, un executor que dispone, especialistas que hacen cada cosa.

## Objetivo del módulo

Al terminar, el alumno puede:

- Separar *planificar* (LLM) de *ejecutar* (código o un segundo LLM) y explicar qué se gana
  en auditabilidad y seguridad.
- Elegir, con argumentos, entre un plan como JSON de tools (catálogo cerrado) y un plan como
  código (expresivo pero inseguro).
- Armar un equipo de agentes con roles, un router y un historial compartido, y estimar su
  costo en llamadas.
- Validar siempre lo que devuelve un LLM (`json.loads` con limpieza, chequeos de tipo,
  `ValueError` legibles) y nunca `eval()`.

## Labs, en orden

| Lab | Qué se construye | Stack | Huecos | Costo por corrida |
|---|---|---|---|---|
| [01-atencion-cliente-tools](01-atencion-cliente-tools/) | Planner → Reflector → Executor → Explicador para una tienda de anteojos. El plan es JSON y solo puede usar 8 tools. | SDK `openai`, pandas + DuckDB, `response_format=json_object` | 6 | ~10 llamadas |
| [02-atencion-cliente-codigo](02-atencion-cliente-codigo/) | La misma tienda, pero el LLM escribe Python que es el plan y se ejecuta con `exec()`. Incluye la discusión de por qué ese sandbox no es seguro. | SDK `openai`, TinyDB | 7 | ~4 llamadas |
| [03-equipo-investigacion](03-equipo-investigacion/) | Planner → Executor que rutea a Research (con tools) / Writer / Editor, con historial, hasta un informe en Markdown. | `aisuite`, `research_tools` (arXiv, Tavily, Wikipedia) | 8 (5 funciones) | **15–25 llamadas** |

Cada carpeta tiene `notebook_alumno.ipynb`, `notebook_solucion.ipynb`, `workbook.md`,
`guia_docente.md`, `tests.py` (correr `pytest -q` adentro de la carpeta, o `run_all` desde
el notebook) y los helpers dados.

## Reparto en sesiones de 3 horas

### Sesión 1 (180 min) — Planificar vs. ejecutar

| Min | Bloque |
|---|---|
| 0–10 | Apertura del módulo: de un agente a un equipo. Qué cambia respecto de M3/M4. |
| 10–90 | **Lab 01** (80 min, ver su guía minuto a minuto). Quiz, teoría, los 6 huecos, los tres casos. |
| 90–100 | Pausa. |
| 100–180 | **Lab 02** (80 min). Quiz, comparación con el lab 01, los 7 huecos, sección de seguridad del sandbox **en vivo**, los tres casos. |

Cierre de la sesión: pedir que para la próxima lean la sección 1 del workbook del lab 03 y
piensen qué métrica usarían para evaluar un pipeline de varios agentes.

### Sesión 2 (180 min) — Equipos de agentes y proyecto de cierre

| Min | Bloque |
|---|---|
| 0–100 | **Lab 03** (100 min, ver su guía). Quiz, teoría, los 8 huecos sobre `PLAN_CORTO`, `run_all`, y **una sola** corrida completa en vivo. |
| 100–110 | Pausa. |
| 110–165 | **Proyecto de cierre del módulo** (55 min, en grupos de 2 o 3): ver abajo. |
| 165–180 | Puesta en común: cada grupo muestra su pipeline en 3 minutos y dice cuánto costó en llamadas. |

### Proyecto de cierre (sesión 2, 55 min)

Consigna: *"Elegí un dominio chico (una biblioteca, un gimnasio, un servicio de delivery) y
armá un pipeline de al menos tres roles que atienda tres pedidos: uno de lectura, uno que
modifica estado y uno que tiene que fallar."*

Requisitos mínimos:

1. Un planner que devuelve JSON validado (del lab 01 o del lab 03, a elección).
2. Un executor que **no** es un LLM, o que rutea a funciones por nombre (lab 03).
3. Al menos una validación que el executor haga por su cuenta, aunque el plan no la pida.
4. Un caso que falle y una explicación legible del fallo.
5. Una línea en el README del grupo con el costo en llamadas de atender los tres pedidos.

Lo que se evalúa es el diseño, no la cantidad de código: se espera que reutilicen
`tools.py` del lab 01 o `inv_utils.py` del lab 02 cambiando los datos.

## Prerrequisitos

- Haber hecho M3 (tools con aisuite y con el SDK de OpenAI) y M4 (evaluación por componente,
  `research_tools`).
- Python: dicts anidados, `json.loads`/`json.dumps`, `try/except`, `exec` (se explica en el
  lab 02), pandas básico (`copy`, `loc`, `concat`).
- `.env` en la raíz con `OPENAI_API_KEY`. `TAVILY_API_KEY` opcional (lab 03 cae a Wikipedia).
- Red para arXiv y Wikipedia en el lab 03.
- Dependencias: ya están en `requirements.txt` de la raíz (`duckdb`, `tinydb`, `aisuite`).

## Qué se evalúa

- **Labs 01 y 02:** no se califican formalmente (eran ungraded en el original). Sus guías
  traen una rúbrica opcional. Lo mínimo exigible es que `run_all` pase.
- **Lab 03:** es el lab evaluable del módulo. Rúbrica detallada de 100 puntos en su
  `guia_docente.md` (55 puntos se verifican con `run_all` y lectura de código; 45 con la
  corrida completa y el informe). Umbral sugerido: 60, con planner, ruteo e historial
  obligatorios.
- **Proyecto de cierre:** se evalúa en la puesta en común con los cinco requisitos como
  checklist.

## Decisiones de diseño del módulo (para quien mantenga el material)

- Modelos siempre desde `.env`: `MODEL_CHEAP` para generar, rutear y explicar;
  `MODEL_STRONG` para reflexionar, criticar y planificar en el lab 03. Nunca `o4-mini` ni
  `gpt-4o` (el original los usaba).
- Prompts en español; queries a arXiv/Tavily en inglés con nota.
- `research_tools.py` del lab 03 es una copia de `comun/research_tools.py`; si se corrige un
  bug, corregirlo en `comun/` y volver a copiar.
- Los tres `tests.py` corren sin API. Los del lab 03 usan un `FakeClient` con la forma real
  de la respuesta de aisuite (`choices[0].message.content` e `intermediate_messages`).
- `data/store_db.json` del lab 02 se regenera con `inv_utils.seed_db()`; se puede borrar.
  `data/informe.md` del lab 03 lo crea la corrida completa.

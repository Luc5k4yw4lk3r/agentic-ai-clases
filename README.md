# Agentic AI — labs para clase

Adaptación para el bootcamp de AI Engineering de los labs del curso *Agentic AI*
de DeepLearning.AI (Andrew Ng): patrones de **reflexión**, **tool use**,
**evaluación** y **multi-agente**, traducidos, convertidos en ejercicios con
huecos, con quiz de apertura, workbook, guía docente y rúbricas.

| Módulo | Labs | Sesiones de 3 h |
|---|---|---|
| [M2 · Reflection](M2-reflection/README.md) | 01 ensayo · 02 SQL · 03 gráficos (visión) | 2 |
| [M3 · Tool Use](M3-tool-use/README.md) | servidor de email · 01 email assistant (aisuite) · 02 research agent (function calling a mano) | 2 |
| [M4 · Evaluación](M4-evaluacion/README.md) | 01 evaluar la búsqueda · 02 la app de referencia (lectura + caza de bugs) | 1 |
| [M5 · Multi-agente](M5-multiagente/README.md) | 01 atención al cliente con tools · 02 "code as action" · 03 equipo de investigación | 2 |

Secuencia completa sugerida: **7 sesiones** (ver cada README de módulo para el
minuto a minuto). Cada módulo cierra con una consigna de proyecto corto.

## Setup (una vez, antes de la primera clase)

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements.txt
cp .env.example .env            # completar OPENAI_API_KEY (y TAVILY_API_KEY si la usás)
python setup/check_env.py       # agregá --llamar para hacer una llamada de prueba
```

Cada lab es una carpeta autocontenida: se abre `notebook_alumno.ipynb` desde
esa carpeta (Jupyter o VS Code) y el `.env` se encuentra solo porque los
notebooks hacen `load_dotenv(find_dotenv(usecwd=True))`.

## Modelos y fecha de caducidad

Los labs originales usan `o4-mini`, `gpt-4o`, `gpt-4.1` y `gpt-4.1-mini`.
Según la [página de deprecaciones de OpenAI](https://developers.openai.com/api/docs/deprecations),
**`o4-mini` se apaga el 23 de octubre de 2026** y **`gpt-4o`/`gpt-4.1`/`gpt-4.1-mini`
el 14 de enero de 2027** (reemplazo sugerido: `gpt-6-luna`).

Por eso ningún notebook tiene un modelo escrito adentro: se leen del `.env`.

| Variable | Default | Rol en los labs |
|---|---|---|
| `MODEL_CHEAP` | `gpt-4.1-mini` | generar, llamar tools, rutear |
| `MODEL_STRONG` | `gpt-4.1` | reflexionar, criticar, ver imágenes (M2-03) |

Los defaults funcionan hasta el 14/01/2027 y es el stack sobre el que está
probado el function calling de `aisuite` (Chat Completions). Para migrar a la
familia GPT-6 cambiá las dos variables; tené en cuenta que, según la
documentación de terceros disponible al cierre de este material, en los modelos
GPT-6 el tool calling por Chat Completions requiere `reasoning_effort="none"`
(Sol/Luna) o directamente la Responses API (Astra, 6.1 Sol). Antes de la primera
clase con el stack nuevo, corré `python setup/check_env.py --llamar` y el lab
M3-01 completo.

`o4-mini` se usaba en el original como "modelo que razona" para reflexionar; acá
ese rol lo cumple `MODEL_STRONG`. No pases `temperature` si configurás un modelo
de razonamiento: muchos la rechazan.

## Claves y costos

- `OPENAI_API_KEY`: todos los labs.
- `TAVILY_API_KEY`: solo M3-02, M4-01, M5-03 y la app. Si falta, las tools caen
  a Wikipedia automáticamente (`comun/research_tools.py`), así que la clase no
  se frena. Si toda la clase comparte una key de Tavily, el plan gratuito se
  agota rápido: mejor una key por alumno o correr esos labs en vivo.
- Costo orientativo por corrida completa con los defaults: M2 y M3-01 centavos;
  M3-02 y M4-01 ~5-10 llamadas; M5-03 y la app ~15-25 llamadas. La guía docente
  de cada lab tiene el detalle y la estrategia (qué corre el profesor una vez,
  qué corren los alumnos con planes cortos).

## Flujo de trabajo del profesor

```
lab.py  ──build_nb.py──►  notebook_alumno.ipynb + notebook_solucion.ipynb
```

- **Editar un lab:** se edita `lab.py` (formato percent de Jupytext; los huecos
  van entre `### BEGIN SOLUTION` / `### END SOLUTION`, ver `CONVENCIONES.md`) y
  se regenera con `python tools/build_nb.py <ruta>/lab.py` o `--all`. Los
  `.ipynb` no se editan a mano.
- **Repartir a los alumnos:** `python tools/export_alumnos.py` arma
  `dist/alumnos/` sin soluciones, guías ni fuentes. Ese directorio es lo que se
  sube al repo o al drive de la cohorte.
- **Verificar todo:** `python tools/build_nb.py --all && python tools/run_tests.py`
  desde la raíz corre el build, la compilación de cada celda y los tests que no
  necesitan API (cada lab en su propia carpeta, para que los `utils.py` no
  choquen entre sí).
- **Mantener:** `CONVENCIONES.md` fija voz, estructura y reglas de los huecos;
  `tools/BRIEF_GENERADOR.md` es el brief con el que se generó cada módulo y
  sirve para generar uno nuevo con el mismo formato.

## Qué cambió respecto del material original

Cada `guia_docente.md` tiene una sección "Diferencias con el lab original". Lo
transversal:

- Traducción al español (voz "vos"), prompts al modelo también en español.
- Casi todo el original venía resuelto; acá cada lab tiene entre 3 y 6 huecos
  graduados, con celda de prueba después de cada función.
- Se corrigieron bugs del original: parseo de JSON entre fences que fallaba en
  silencio, query de arXiv sin codificar, `utils (1).py` sin renombrar,
  dependencias no declaradas (`tabulate`, `duckdb`), comparación de dominios por
  substring, `eval()` sobre salida del modelo, PNGs viejos que ocultaban fallas.
- El servidor FastAPI del lab de email (M3) no estaba en el repo: se
  reconstruyó, con tests.
- La app de referencia se dejó corriendo con modelos desde `.env` y dos bugs de
  comportamiento intactos como ejercicio de caza de bugs.
- Los graded labs de M3 y M5 no tenían autograder: se agregaron `tests.py` con
  clientes simulados y rúbricas.

## Estructura

```
.
├── README.md  CONVENCIONES.md  requirements.txt  .env.example
├── setup/check_env.py
├── tools/build_nb.py  tools/run_tests.py  tools/export_alumnos.py  tools/BRIEF_GENERADOR.md
├── comun/research_tools.py          # tools compartidas (arXiv, Wikipedia, Tavily con fallback)
├── M2-reflection/   M3-tool-use/   M4-evaluacion/   M5-multiagente/
│   └── NN-<lab>/  lab.py  notebook_alumno.ipynb  notebook_solucion.ipynb
│                  workbook.md  guia_docente.md  utils.py  tests.py  data/
└── dist/alumnos/                    # generado por tools/export_alumnos.py
```

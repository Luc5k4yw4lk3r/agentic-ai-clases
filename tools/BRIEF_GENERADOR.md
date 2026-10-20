# Brief para generar un módulo del material

Leé primero `CONVENCIONES.md` (raíz) completo. Después este brief. Después el
material original del módulo que te toca.

## Dónde está cada cosa

- Material original (solo lectura, NO modificar):
  `/home/claude/madeeha96/agentic-ai/`
- Material nuevo (donde escribís): `/home/claude/agentic-ai-clases/`
- Build de notebooks: `python3 tools/build_nb.py <ruta/lab.py>` desde la raíz
  del material nuevo. Tiene que imprimir `OK` y la cantidad de huecos.
- Dependencias ya instaladas en este entorno (ver `requirements.txt`). No
  agregues paquetes nuevos sin necesidad real; si agregás uno, sumalo a
  `requirements.txt` con un comentario. El paquete `wikipedia` NO está
  disponible: Wikipedia se consulta con `requests` contra la API de MediaWiki
  (`https://en.wikipedia.org/w/api.php`, `action=query&list=search` y
  `prop=extracts`).
- No hay API keys en este entorno: no vas a poder ejecutar llamadas a OpenAI
  ni a Tavily. Todo lo demás (utils, tests sin API, servidores, parsers, DBs)
  **sí** se prueba ejecutándolo.

## Qué entregás por cada lab

```
Mx-<tema>/NN-<slug>/
  lab.py                 fuente del notebook (percent + BEGIN/END SOLUTION)
  notebook_alumno.ipynb  generado con build_nb.py
  notebook_solucion.ipynb generado
  workbook.md            formato workbook (CONVENCIONES §5)
  guia_docente.md        (CONVENCIONES §6)
  utils.py               helpers dados; probados
  tests.py               si el lab se evalúa (CONVENCIONES §7)
  data/                  datasets copiados del original (csv, db, json). NO copiar
                         logos ni imágenes con marca; los diagramas se describen
                         en texto o se dibujan en Mermaid dentro del markdown.
```

Y un `Mx-<tema>/README.md` con: objetivo del módulo, labs en orden, cómo se
reparten en sesiones de 3 h (el bootcamp tiene sesiones de 3 h), prerrequisitos
y qué se evalúa.

## Celdas estándar al inicio de cada `lab.py`

```python
# %% [markdown]
# # <Título>
# **Módulo X · Lab NN.** <una línea de qué se construye>
#
# ## Objetivos
# Al terminar vas a poder:
# - ...
# - ...

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
# 1. ...   a) ...  b) ...  c) ...
# (5 preguntas: 2 de repaso de la sesión anterior, 2 del concepto nuevo, 1 de base)

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (porque ...), 2-a (...), ...

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"
```

- Con `aisuite`: `import aisuite as ai` / `client = ai.Client()` y el modelo se
  pasa como `f"openai:{MODEL_CHEAP}"`. Dentro de las funciones, el parámetro
  `model` recibe ya el string completo (`"openai:gpt-4.1-mini"`); definí una
  constante `AI_CHEAP = f"openai:{MODEL_CHEAP}"` y `AI_STRONG = ...` en la celda
  de setup y usalas como defaults.
- Con el SDK `openai` directo: `from openai import OpenAI` / `client = OpenAI()`
  y el modelo sin prefijo.
- **Nunca** `o4-mini`, `o3`, `gpt-4o`, `gpt-4o-mini` ni `temperature` con
  modelos de razonamiento. Si el original usaba `o4-mini` para "razonar", acá
  va `MODEL_STRONG`. Si el original usaba `response_format={"type":
  "json_object"}`, se mantiene (funciona en gpt-4.1).
- Los prompts al LLM se escriben en **español** (los alumnos tienen que poder
  leerlos y modificarlos). Excepción: queries a arXiv/Tavily/Wikipedia en inglés,
  con una nota de por qué.

## Cómo se vacía un lab para convertirlo en ejercicio

1. Identificá las 3 a 6 funciones que encarnan la idea del lab (no los helpers).
2. Para cada una: la firma, los type hints, el docstring y los comentarios
   `# Paso n:` quedan a la vista; la lógica de cada paso va en su propio bloque
   `### BEGIN SOLUTION ... ### END SOLUTION`.
3. Gradualidad dentro del notebook: el primer hueco es casi copiar el ejemplo
   resuelto de la celda anterior; el último exige combinar dos cosas. Si el lab
   original no tenía nada resuelto, agregá vos una celda de "ejemplo resuelto"
   con la misma estructura antes del primer hueco.
4. Después de cada función con huecos: celda de prueba mínima que muestre algo
   concreto (un `print`, un `display`).
5. Extensión opcional: va en el workbook y como última sección del notebook
   ("Si te sobra tiempo"), sin huecos, con consignas abiertas.

## Calidad: qué verifico antes de darlo por terminado

- `python3 tools/build_nb.py <lab.py>` → `OK`.
- `python3 -m py_compile` de `utils.py` y `tests.py`.
- Los tests que no requieren API corren verdes con `pytest -q` dentro de la
  carpeta del lab.
- Ejecuté a mano los helpers de `utils.py` con los datos de `data/` (cargar el
  CSV, crear la DB, parsear un JSON de ejemplo, etc.) y funcionan.
- Las funciones de la solución las revisé contra un `response` simulado (un
  objeto con la misma forma que devuelve el SDK) para asegurar que la lógica de
  parseo es correcta. Para aisuite, `response.choices[0].message.content` y
  `response.choices[0].intermediate_messages` (lista de mensajes del loop de
  tools) son la forma real.
- Ningún texto en inglés quedó sin traducir en markdown (salvo términos
  técnicos). Ningún emoji en el cuerpo. Ningún `TODO` ni `[Completar...]` sin
  justificar.
- `guia_docente.md` incluye la sección "Diferencias con el lab original" con
  los bugs del original que corregiste.

## Lo que NO hacés

- No tocás carpetas de otros módulos ni los archivos de la raíz
  (`README.md`, `requirements.txt`, `CONVENCIONES.md`, `tools/`). Si algo de
  la raíz debería cambiar, lo decís en tu reporte final.
- No reproducís texto literal largo del material original: se traduce y se
  reescribe con la voz de las convenciones.
- No inventás resultados de ejecución. Si en el workbook mostrás "salida
  esperada", la marcás como *ejemplo ilustrativo (varía entre corridas)*.

## Reporte final (tu último mensaje)

Lista de archivos creados, cantidad de huecos por notebook, qué probaste y
cómo, qué quedó pendiente o con `[Completar por el profesor: ...]`, y cualquier
decisión que convenga revisar. Menos de 400 palabras.

# Convenciones del material "Agentic AI — labs para clase"

Este documento fija cómo se escribe cada lab. Lo leen los generadores (humanos o
agentes) antes de producir material y sirve para mantenerlo después.

## 1. Audiencia y voz

- Alumnos del bootcamp de AI Engineering de Neoland: junior/mid, **poca
  experiencia en Python**, sin background técnico fuerte. Muchos no refrescaron
  Python; el concepto de API les cuesta.
- Español rioplatense neutro, voz **"vos"**. Términos técnicos en inglés cuando
  es el estándar de la industria (prompt, tool, function calling, endpoint,
  schema, loop). No se traducen nombres de funciones ni de parámetros.
- Tono profesional pero cercano. Sin relleno, sin emojis en el cuerpo (se
  permite uno en títulos de sección si ayuda a escanear).
- Cada concepto nuevo se presenta con el trío **para qué / por qué así / ejemplo
  práctico** antes del código.
- Regla anti-relleno: si falta un dato, se escribe
  `[Completar por el profesor: ...]`; nunca se inventa.

## 2. Estructura de cada lab

```
Mx-<tema>/NN-<slug>/
  lab.py                  # FUENTE ÚNICA del notebook (formato percent, ver §3)
  notebook_alumno.ipynb   # generado por tools/build_nb.py — NO editar a mano
  notebook_solucion.ipynb # generado — NO editar a mano
  workbook.md             # material de acompañamiento para el alumno (§5)
  guia_docente.md         # para el profesor (§6)
  utils.py                # helpers que vienen dados (sin lógica del ejercicio)
  tests.py                # cuando el lab se evalúa: chequeos ejecutables (§7)
  data/ ...               # datasets, DBs, imágenes
```

El notebook es lo que se ejecuta en clase; el workbook es lo que se lee antes,
durante y después. No se duplican: el workbook explica y propone práctica
graduada; el notebook tiene el código guiado.

## 3. Formato de `lab.py` (fuente del notebook)

Formato **percent** de Jupytext:

```python
# %% [markdown]
# ## 1. Título de sección
# Texto en markdown, cada línea con `# ` adelante.

# %%
import json          # celda de código normal

# %% [markdown] solo-profesor
# Esta celda se elimina del notebook del alumno (respuestas del quiz, notas).

# %%
def generar_borrador(prompt: str, model: str = MODEL_STRONG) -> str:
    """Docstring visible en ambas versiones."""
    ### BEGIN SOLUTION
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
    ### END SOLUTION
```

Reglas:

- Todo lo que está entre `### BEGIN SOLUTION` y `### END SOLUTION` aparece en
  `notebook_solucion.ipynb` y se reemplaza en `notebook_alumno.ipynb` por:
  ```python
  # ======== TU CÓDIGO ACÁ ========
  raise NotImplementedError("Completá esta función")
  ```
- Si querés un placeholder distinto para el alumno, dentro del bloque usá líneas
  que empiecen con `### STUDENT:`; esas líneas (sin el prefijo) son las que ve el
  alumno, y las demás son la solución. Ejemplo:
  ```python
  ### BEGIN SOLUTION
  ### STUDENT: respuesta = None  # Pista: usá client.chat.completions.create(...)
  respuesta = client.chat.completions.create(...)
  ### END SOLUTION
  ```
- Un bloque de solución nunca abarca una función entera con su `def`: la firma,
  los type hints y el docstring quedan fuera del bloque para que el alumno los
  vea.
- Máximo **una idea por hueco**. Si una función requiere tres pasos, se escriben
  tres bloques BEGIN/END con comentarios `# Paso 1: ...` fuera de cada bloque.
- La celda inmediatamente posterior a una función con hueco es siempre una celda
  de prueba rápida (ejecutar la función con un ejemplo mínimo y mostrar algo).
- Cada notebook arranca con las mismas tres celdas: título + objetivos, quiz de
  apertura (ver §4), setup (imports, `load_dotenv`, lectura de `MODEL_CHEAP` /
  `MODEL_STRONG`).
- Las claves y los modelos salen **siempre** del entorno. Nunca hardcodear un
  nombre de modelo dentro de una función; se pasa por parámetro con default
  `MODEL_CHEAP` o `MODEL_STRONG`.
- Toda llamada a un LLM que genera código o JSON va seguida de validación
  explícita y de un mensaje de error legible. Nada de `if match:` que falla en
  silencio: se levanta `ValueError` con una explicación en español.
- Código **simple antes que elegante**: nada de comprehensions anidadas,
  `getattr` en cadena ni decoradores si un `for` con `if` alcanza. Los alumnos
  tienen que poder leerlo en voz alta.

## 4. Quiz de apertura

5 preguntas de opción múltiple al inicio de cada notebook y del workbook. Mezcla:
2 de repaso de la sesión anterior (repaso espaciado), 2 del concepto nuevo
(responden después de leer la teoría breve), 1 de Python/HTTP/SQL de base que el
lab asume. Las respuestas van en una celda `solo-profesor` y en la guía docente.

## 5. `workbook.md` — formato workbook

```
# <Título del lab>
## Antes de empezar (quiz de 5 preguntas)
## 1. Teoría breve         # 1–2 pantallas. Para qué / por qué así / ejemplo
## 2. Ejemplo resuelto      # un caso completo, con salida esperada comentada
## 3. Práctica graduada
### Nivel base             # lo que hace todo el grupo en clase (obligatorio)
### Extensión opcional     # para los que terminan antes o para la casa
## 4. Troubleshooting de más a menos   # 4–6 errores típicos: síntoma → causa → arreglo
## 5. Para cerrar          # 3 preguntas de reflexión + checklist de autoevaluación
```

Los ejercicios del nivel base se corresponden uno a uno con los huecos del
notebook. La extensión opcional propone modificaciones que no están resueltas en
el notebook (cambiar prompts, agregar una tool, medir algo).

## 6. `guia_docente.md`

```
# Guía docente — <Título>
## Ficha             # duración, prerrequisitos, keys, archivos, costo estimado en llamadas
## Secuencia sugerida (minuto a minuto para una sesión de 3 h o el bloque que ocupe)
## Qué hacer en vivo vs. qué dejan corriendo los alumnos
## Dónde se traban (y qué decir)      # desde el inventario del material original
## Respuestas del quiz de apertura
## Soluciones de la extensión opcional (esbozo)
## Rúbrica           # solo si el lab se evalúa
## Diferencias con el lab original de DeepLearning.AI   # qué se cambió y por qué
```

## 7. `tests.py`

Funciones `test_*` que se pueden correr con `pytest -q` o importar desde el
notebook (`from tests import run_all; run_all(generar_borrador, ...)`). Chequean
tipos, estructura y comportamiento observable sin depender del texto exacto que
devuelve el LLM. Si un test necesita una llamada a la API, se marca con un
comentario `# requiere API` y la función `run_all` las agrupa al final.

## 8. Stack y modelos

- Python 3.11+. Dependencias en `requirements.txt` de la raíz (una sola para
  todo el material).
- Proveedor: OpenAI. Cliente `aisuite` (`openai:<modelo>`) en los labs que lo
  usaban originalmente, SDK `openai` directo en los que enseñan function calling
  "a mano".
- Modelos: se leen del `.env`:
  - `MODEL_CHEAP` (default `gpt-4.1-mini`): generación, tools, ruteo.
  - `MODEL_STRONG` (default `gpt-4.1`): reflexión, crítica, visión.
  - Nunca `o4-mini` ni `gpt-4o` (ver `README.md` → "Modelos y fecha de
    caducidad").
- `TAVILY_API_KEY` solo en los labs que buscan en la web (M3 graded, M4, M5
  graded). Siempre con un fallback a Wikipedia/arXiv si la key falta.

## 9. Diferencias respecto del material original

El material original es el del curso *Agentic AI* de DeepLearning.AI. Cada lab
lo adapta: traduce, reordena, vacía funciones para convertirlo en ejercicio,
corrige inconsistencias del original y agrega quiz, workbook y guía. En la guía
docente se listan los cambios. Se conservan los datasets y la idea pedagógica.

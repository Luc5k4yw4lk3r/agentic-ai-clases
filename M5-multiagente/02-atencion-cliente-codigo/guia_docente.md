# Guía docente — Atención al cliente con código como plan (M5 · Lab 02)

## Ficha

- **Duración:** 80 minutos (segunda mitad de la sesión 1 del módulo, después del lab 01).
- **Prerrequisitos:** lab 01 de M5 (la comparación es el hilo del lab). Python: `exec`,
  `dict.get`, `re.search`, `try/except`. No hace falta conocer TinyDB: se enseña en 5 minutos.
- **Keys:** `OPENAI_API_KEY`. No usa Tavily.
- **Archivos:** `lab.py` → notebooks, `inv_utils.py`, `utils.py`, `tests.py`, `pytest.ini`,
  `workbook.md`, `data/store_db.json` (lo regenera `inv_utils.seed_db()`; se puede borrar).
- **Modelos:** solo `MODEL_CHEAP` (generación de código). `MODEL_STRONG` queda definido
  por convención pero no se usa; es un buen candidato para la extensión del revisor.
- **Costo estimado:** 1 llamada por pedido. Corrida completa del notebook: 4 llamadas.

## Secuencia sugerida (80 min)

| Min | Qué | Cómo |
|---|---|---|
| 0–5 | Quiz de apertura | Las preguntas 1 y 2 repasan el lab 01 recién hecho. La 5 anticipa `__builtins__`. |
| 5–15 | Teoría: tabla comparativa lab 01 vs lab 02 | Arrancar con el pedido "redondos de menos de $100" y preguntar: ¿con qué tool del lab 01 lo resolvés? No hay. Ahí entra el código. |
| 15–25 | Secciones 2 y 3: TinyDB en 3 operaciones y el prompt | Ejecutar en vivo. Leer el prompt en voz alta: dónde están las reglas de negocio ahora. Generar el código del pedido de redondos **sin ejecutarlo** y leerlo juntos. |
| 25–38 | Huecos 1–2: extraer | Mostrar primero `extraer_bloque_plan` (resuelto). Los alumnos copian el patrón. Probar el caso sin etiquetas. |
| 38–55 | Huecos 3–5: ejecutar | Insistir en "un solo dict" y "el traceback se muestra". Correr `CODIGO_A_MANO` y el roto. Después ejecutar el código generado en 3. |
| 55–65 | Sección 6: el sandbox que no es sandbox | **En vivo, sin huecos.** Correr `CODIGO_CURIOSO` sin restricciones (lee el archivo) y con `ejecutar_codigo_restringido` (falla). Nombrar prompt injection. |
| 65–72 | Huecos 6–7: agente completo | Son dos líneas de orquestación. |
| 72–80 | Sección 8: los tres casos | Reseed en el primero. Mirar las tablas después de cada uno. Cerrar con `run_all`. |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

- **En vivo:** la teoría comparativa, la generación del primer código (leerlo antes de
  ejecutarlo es la escena del lab), y toda la sección 6. La sección 6 es la parte que más
  se olvida si se deja para la casa.
- **Alumnos:** los 7 huecos y los tres casos. Si el tiempo aprieta, dar resueltos los
  huecos 6 y 7 (son orquestación) y priorizar los de ejecución (3–5).

## Dónde se traban (y qué decir)

1. **`NameError` dentro de una lambda del código generado.** Pasaron dos dicts a `exec`.
   Decir: "las lambdas buscan en globals; con dos dicts, `tope` quedó en locals". Es el bug
   más instructivo del lab; vale la pena que alguien lo cometa.
2. **"`status` es `None` pero no hay error".** El código generado puso `STATUS` dentro de
   un `if`. Mirar `resultado["codigo"]`. Pedir que agreguen al prompt "definí STATUS antes
   de cualquier if".
3. **El traceback se guarda pero no se ve.** Olvidaron el `print` en el `except`. El test
   `test_ejecutar_error_devuelve_traceback_y_lo_muestra` lo detecta con `capsys`. Decir:
   "un agente que falla en silencio es peor que uno que falla a los gritos".
4. **Corren la devolución dos veces y Aviator queda en 27.** TinyDB persiste en disco.
   `reseed=True` o `inv_utils.seed_db()`.
5. **Confunden "controlar el namespace" con "controlar qué puede hacer".** Es el punto de
   la sección 6. Si alguien dice "pero le pasamos solo las tablas", mostrar
   `print(sorted(namespace["__builtins__"]))` después del `exec`: están todos.
6. **Preguntan por qué no usar siempre este patrón si es más expresivo.** Volver a la tabla:
   catálogo cerrado vs. prompt como barrera. Decir que en producción el patrón se usa, pero
   con ejecución remota aislada, y que elegir entre los dos labs es una decisión de diseño.
7. **El modelo envuelve el código en ```python``` dentro de las etiquetas.** Está
   contemplado (`utils.quitar_fences`); si aparece, es un buen ejemplo de por qué el
   contrato de salida se valida en vez de asumirse.

## Respuestas del quiz de apertura

1. **c** — el executor era código puro.
2. **b** — el registro cerrado rechazaba el nombre con `ValueError`.
3. **a** — el código generado es el plan y se corre con `exec()`.
4. **b** — Python compone filtros; no hace falta una tool por combinación.
5. **b** — `exec` escribe en el dict y Python agrega `__builtins__` completo si no estaba.
   Ese agregado automático es el agujero de la sección 6.

## Soluciones de la extensión opcional (esbozo)

- **Intención no soportada:** gpt-4.1-mini suele devolver `unsupported_intent` y ofrecer
  "modelos nuevos similares". Si devuelve `invalid_request`, es defendible; discutir la
  diferencia entre las dos.
- **Stock insuficiente:** el prompt dice "no modifiques nada". Con 10 Mystique + 1 Aviator
  el modelo casi siempre valida todo antes de insertar. Si alguna vez inserta la fila de
  Aviator y después frena, es exactamente la clase de bug que en el lab 01 el executor
  impedía por construcción. Señalarlo.
- **Ejecutor restringido:** los códigos del modelo usan `sorted`, `round`, `float`, `len`,
  `f-strings` (no necesitan builtin) y a veces `next`. `next` no está en la lista: agregarlo
  es la respuesta típica.
- **Revisor con `ast`:**
  ```python
  import ast
  PROHIBIDAS = {"open", "eval", "exec", "__import__", "compile", "getattr", "globals"}
  def revisar_codigo(codigo):
      motivos = []
      for nodo in ast.walk(ast.parse(codigo)):
          if isinstance(nodo, (ast.Import, ast.ImportFrom)):
              motivos.append("import no permitido")
          if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in PROHIBIDAS:
              motivos.append(f"llamada a {nodo.func.id}")
          if isinstance(nodo, ast.Attribute) and nodo.attr.startswith("__"):
              motivos.append(f"acceso a {nodo.attr}")
      return motivos
  ```
  Aclarar que tampoco es seguridad completa (strings construidos, `getattr` por nombre).
- **Prompt injection:** gpt-4.1-mini normalmente ignora la instrucción del cliente, pero no
  siempre. El punto no es si obedece hoy: es que la única barrera es el modelo.

## Rúbrica

El lab no se califica formalmente (ungraded en el original). Si se evalúa:

| Criterio | Puntos | Cómo se verifica |
|---|---|---|
| `run_all(extraer_bloque_ejecutable, ejecutar_codigo_generado)` pasa los 14 tests | 40 | Celda final |
| `extraer_bloque_ejecutable` levanta `ValueError` en español sin etiquetas | 10 | Test + lectura |
| `ejecutar_codigo_generado` usa un solo dict, captura stdout y muestra el traceback | 20 | Tests `lambda_ve_variables` y `traceback_y_lo_muestra` |
| `agente_atencion` orquesta y devuelve el dict completo; acepta `ejecutor` alternativo | 10 | Correr con `ejecutar_codigo_restringido` |
| Los tres casos dan el efecto esperado en las tablas | 10 | Aviator 25 tras la devolución; dos filas tras la compra doble |
| Puede explicar oralmente por qué el sandbox no es seguro y nombrar una mitigación real | 10 | Pregunta de cierre |

## Diferencias con el lab original de DeepLearning.AI

El original es `M5_UGL_1_R.ipynb` ("Customer Service Agent", code as action), resuelto.

- **Vaciado en 7 huecos** (extraer ×2, ejecutar ×3, agente ×2). `generar_codigo` y el
  prompt se dan resueltos porque el foco del lab es extraer/ejecutar, no el prompt.
- **Modelos:** el original usaba `o4-mini` con `temperature=1.0` y `gpt-4.1-mini` con
  `temperature=0.2` según la celda. Acá `MODEL_CHEAP` desde `.env` y sin `temperature`.
- **Prompt en español**, con el mismo contrato (`<execute_python>`, `STATUS`,
  `answer_text`) y las mismas reglas de negocio. Las descripciones de los productos se
  tradujeron, y el filtro de forma del marco usa "redondo" en la descripción.
- **Ejecución:**
  - `exec` con **un solo dict**. El original usaba `SAFE_GLOBALS` y `SAFE_LOCALS`
    separados, lo que hacía que lambdas y funciones del código generado no vieran las
    variables del nivel superior (`NameError`). Hay un test que lo cubre.
  - El traceback **se imprime**. El original lo guardaba en `result["error"]` y la celda
    siguiente mostraba `result["answer"]` (`None`) sin explicar nada.
  - Se devuelven `status` y `answer_text` por separado en vez de `answer = answer_text or
    answer_rows or answer_json`, que mezclaba tipos.
  - Se agregó `datetime` al namespace: el prompt original pedía un timestamp pero no lo
    proveía, y el modelo tenía que importarlo (violando su propia regla de "sin imports").
- **Extracción:** si no hay etiquetas se levanta `ValueError`; el original asumía que el
  texto completo era código. Se agregó `utils.quitar_fences` para el caso de ```python```
  dentro de las etiquetas.
- **`inv_utils.py`:** el original abría `store_db.json` **al importar el módulo** (en el
  directorio actual, no en `data/`) y `create_inventory()` escribía sobre esas tablas
  globales; `seed_db()` abría *otro* `TinyDB` con el mismo path. Como consecuencia,
  `reseed=True` en `customer_service_agent` reseteaba un handle distinto del que usaba el
  notebook. Ahora las funciones reciben la tabla como parámetro y la ruta por defecto es
  `data/store_db.json` relativa al lab.
- **Sección 6 (sandbox) es nueva.** El original decía "runs the code in a locked-down
  sandbox" y "safe helpers only"; no era cierto y no lo discutía. Acá se demuestra con
  `open()` y se muestra la mitigación de `__builtins__` junto con sus límites.
- **Se quitaron** los paneles HTML con colores, los emojis del cuerpo y las celdas de
  "inspección manual" repetidas (se condensaron en la sección 2.1).
- **Quiz, workbook, guía y `tests.py`** son nuevos.

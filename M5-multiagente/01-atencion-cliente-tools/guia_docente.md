# Guía docente — Atención al cliente con un plan de tools (M5 · Lab 01)

## Ficha

- **Duración:** 80 minutos (primera mitad de la sesión 1 del módulo).
- **Prerrequisitos:** M2 (reflexión), M3 (function calling, qué es una tool), M4
  (evaluación por componente). Pandas básico: `df.loc`, `copy()`, `concat`.
- **Keys:** `OPENAI_API_KEY`. No usa Tavily.
- **Archivos:** `lab.py` → `notebook_alumno.ipynb` / `notebook_solucion.ipynb`,
  `inventory_utils.py`, `tools.py`, `utils.py`, `tests.py`, `pytest.ini`, `workbook.md`.
  No tiene `data/`: los DataFrames se generan en memoria con semilla fija.
- **Modelos:** `MODEL_CHEAP` para planner y explicador, `MODEL_STRONG` para el reflector.
- **Costo estimado:** 3 llamadas por pedido atendido (planner + reflector + explicador si
  falla) más 3 pruebas rápidas sueltas. Corrida completa del notebook: 10 a 12 llamadas.
  Despreciable con gpt-4.1-mini / gpt-4.1.

## Secuencia sugerida (80 min)

| Min | Qué | Cómo |
|---|---|---|
| 0–5 | Quiz de apertura | Oral o en el chat. Las preguntas 1 y 2 repasan M4. |
| 5–15 | Teoría: roles y "el LLM propone, el código dispone" | Dibujar el pipeline en el pizarrón. Insistir en que el executor no tiene LLM. |
| 15–25 | Secciones 1 a 3 del notebook (datos, catálogo, anatomía del plan) | Ejecutar en vivo. Detenerse en el dibujo de `context.prod.item.price` y correr la celda de `resolve_args` con la clave mal escrita. |
| 25–40 | Hueco 1: executor | Los alumnos completan el Paso 2. Correr `EJEMPLO_PLAN` y `PLAN_MYSTIQUE_SIN_VALIDAR`. Mostrar que `inventory_df` original no cambió. |
| 40–55 | Huecos 2 y 3: planner | Leer juntos `REGLAS_PLANNER`. Completar. Correr con "devolver dos Aviator" e imprimir los pasos. |
| 55–65 | Huecos 4 y 5: reflector | Correr con `BORRADOR_CON_ERRORES`. Leer la crítica en voz alta. |
| 65–72 | Hueco 6: explicador | Correr con `reporte_fallido`. |
| 72–80 | Sección 6: los tres casos de punta a punta | Mystique falla, Aviator y Sport pasan. Reasignar DataFrames. Cerrar con `run_all(ejecutar_plan)`. |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

- **En vivo (profesor):** secciones 1–3 y el primer caso de la sección 6 (Mystique). Son
  las que explican el modelo mental.
- **Alumnos:** los seis huecos y los casos 2 y 3. Los huecos 2 a 6 son casi "copiar la forma
  de la llamada" después de haber visto el ejemplo; el hueco 1 es el que más piensa.
- Si falta tiempo, el hueco 6 (explicador) se puede dar resuelto: es el menos novedoso.

## Dónde se traban (y qué decir)

1. **"Mi plan falla con `context.prod.item.price` no se puede resolver".** Casi siempre es
   que el producto no se encontró: `item` es `None` porque el nombre vino mal o con un
   espacio. Mirar la validación `producto_encontrado` del paso 1 en el reporte. Decir: "el
   error te está diciendo exactamente hasta dónde llegó la ruta".
2. **"Hice la devolución y el inventario sigue igual".** No reasignaron los DataFrames.
   Es el momento de explicar que es una decisión de diseño, no un bug.
3. **Hueco 1: `paso_ok` mal calculado.** Olvidan incluir `error_tool is None` y un paso con
   una tool explotada queda en `ok: True` si las validaciones (que corren igual) pasaron.
   El test `test_executor_tool_desconocida_queda_en_el_reporte` lo detecta.
4. **Hueco 1: agregan el chequeo fijo pero con `any` en vez de `all`.** El test de
   Mystique falla. Pedir que lean en voz alta "el paso pasa si TODAS las validaciones pasan".
5. **El reflector "arregla" el plan metiendo SQL o una tool nueva.** Pasa poco con gpt-4.1
   pero pasa. El executor lo rechaza con `Tool desconocida`. Buena oportunidad para decir
   que el reflector también es un LLM y también se equivoca: por eso el executor es la
   última línea.
6. **`json_object` y el modelo devuelve `{"plan": {...}}`.** El `ValueError` del hueco 3
   lista las claves que llegaron. Reforzar en el prompt que las claves son exactamente
   `reasoning` y `steps`.
7. **Confusión entre `validations` del plan y `validar_stock_no_negativo` del executor.**
   Explicar "defensa en profundidad": una la pide el modelo (puede olvidarse), la otra es
   nuestra (no se negocia).

## Respuestas del quiz de apertura

1. **b** — evaluación a nivel de componente (M4).
2. **b** — objetiva, con ground truth por ejemplo: la lista de dominios preferidos.
3. **b** — el plan solo puede invocar lo que el catálogo permite; cada paso queda
   registrado y revisable antes de ejecutarse.
4. **b** — es una referencia al contexto que resuelve el executor (`resolve_args`).
5. **b** — `copy()` crea un DataFrame independiente; por eso el estado real solo cambia al
   reasignar.

## Soluciones de la extensión opcional (esbozo)

- **`get_low_stock`:** en `tools.py`,
  `def get_low_stock(con, threshold=5): df = con.execute("SELECT name, item_id, quantity_in_stock FROM inventory_df WHERE quantity_in_stock <= ?", [int(threshold)]).df(); return {"rows": df, "items": df.to_dict("records"), "count": len(df)}`.
  Sumar a `TOOL_REGISTRY`, `ARGS_OBLIGATORIOS` (`[]`), `RECURSOS_COMPARTIDOS` (`["con"]`)
  y una línea 9) en `CATALOGO_TOOLS`. El planner la usa si el pedido dice "agotarse" o
  "poco stock"; a veces hace falta agregar un ejemplo de consulta a las reglas.
- **Medir al reflector:** con 5 pedidos bien formados, gpt-4.1 suele dejar 3 o 4 iguales
  y cambiar 1 o 2 (nombres de args, una validación faltante). La conclusión que se busca:
  el reflector vale cuando el planner es barato o el dominio es delicado; si el planner es
  fuerte, conviene medir antes de pagar la segunda llamada.
- **Pedido ambiguo:** agregar a `REGLAS_PLANNER` una regla 7: "Si el pedido no tiene
  producto o cantidad, el plan tiene un solo paso `get_inventory_data` sin filtros y el
  `reasoning` dice qué habría que preguntarle al cliente".
- **Sin reflector:** los tres casos del lab pasan igual la mayoría de las veces con
  gpt-4.1-mini. Eso es un dato: el reflector agrega robustez, no funcionalidad.

## Rúbrica

Este lab no se califica formalmente (era ungraded en el original). Si se quiere evaluar:

| Criterio | Puntos | Cómo se verifica |
|---|---|---|
| `run_all(ejecutar_plan)` pasa los 22 tests | 40 | Correr la celda final |
| `generar_plan` valida `steps` y levanta `ValueError` legible | 15 | Pasarle un pedido vacío o un catálogo vacío |
| `reflexionar_plan` devuelve `critica` y `plan_revisado` y cae al borrador si el JSON viene mal | 15 | Leer el código; probar con `BORRADOR_CON_ERRORES` |
| `explicar_error` produce 2–3 frases en español sin jerga | 10 | Leer la salida con `reporte_fallido` |
| Los tres casos de la sección 6 dan el resultado esperado y el estado se reasigna solo cuando `ok` | 20 | Inventario final: Aviator 25, Sport 1, Mystique 3 |

## Diferencias con el lab original de DeepLearning.AI

El original es `M5_UGL_1.ipynb` ("Customer Service Pipeline"), totalmente resuelto.

- **Vaciado en 6 huecos** (executor acotado, planner ×2, reflector ×2, explicador). El
  resto (tools, registro, resolución de referencias) se mantuvo como código dado.
- **Modelos:** el original usaba `o4-mini` en todo y ofrecía `gpt-4o`. Acá `MODEL_CHEAP`
  para planner/explicador y `MODEL_STRONG` para el reflector, desde `.env`.
- **Prompts en español**, con el catálogo de tools insertado desde `tools.CATALOGO_TOOLS`
  (antes estaba duplicado a mano dentro del prompt y podía desincronizarse del registro).
- **`inventory_utils.py` limpiado:** el original arrastraba ~250 líneas de M3/M4
  (`create_ledger_dataframe`, `update_stock`, `execute_plan_with_reflection`,
  `call_llm_for_reflection` con `gpt-4o` hardcodeado...) que el lab no usaba.
- **`tools.py`:**
  - Se quitaron los alias (`lookup_product`, `propose_transaction`, `project_inventory`,
    `assert`, `assert_non_null`, `assert_gt`) que estaban en el registro pero el prompt
    prohibía: el catálogo que ve el modelo y el registro ahora son exactamente el mismo.
  - `get_from_context` devolvía `None` en silencio si la ruta no existía, lo que producía
    errores confusos dos pasos más tarde. Ahora levanta `ValueError` diciendo hasta dónde
    llegó.
  - Las tools de escritura devolvían `{"error": "item_not_found"}` y el executor seguía
    como si nada (el dict sin `inventory_df` no se aplicaba y nadie lo notaba). Ahora
    levantan `ValueError`.
  - La inyección de `con`/`inventory_df`/`transaction_df` se hace por tabla
    (`RECURSOS_COMPARTIDOS`) en vez de a todas las tools con `setdefault`: así
    `compute_total(qty, price, con, inventory_df, transaction_df)` ya no es posible.
  - `assert_nonnegative_stock` ya no exige `inventory_df_from: "context.__frames__.inventory_df"`
    en el plan (detalle interno del executor que el modelo tenía que adivinar); el executor
    inyecta el DataFrame vigente.
- **Executor:** se agregó `validar_stock_no_negativo` como chequeo fijo independiente del
  plan, y cada paso del reporte tiene su `ok`. El original dependía de que el planner
  pidiera la validación.
- **Reflector:** el original tenía una función de reparación de escapes JSON suelta;
  se movió a `utils.parsear_json` y se usa en los dos agentes que parsean JSON. El
  fallback al borrador ahora avisa con `print` (antes era silencioso).
- **Explicador:** se quita `updated_frames` del reporte antes de mandarlo al modelo
  (el original mandaba el dict con DataFrames adentro vía `f"{execution_report}"`).
- **Quiz, workbook, guía y `tests.py`** son nuevos. El original no tenía pruebas.

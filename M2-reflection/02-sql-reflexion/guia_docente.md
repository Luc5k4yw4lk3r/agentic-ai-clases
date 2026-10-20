# Guía docente — SQL con reflexión: de la pregunta en castellano a la consulta correcta

## Ficha

| | |
|---|---|
| **Duración** | 75 min dentro de la sesión 1 del módulo (ver `M2-reflection/README.md`) |
| **Prerrequisitos** | Lab 01 terminado (llamada con aisuite, pasar datos entre funciones). SQL básico: `SELECT`, `WHERE`, `GROUP BY`, `SUM`. Saber qué es un DataFrame. |
| **Keys** | `OPENAI_API_KEY`. No usa Tavily. |
| **Archivos** | `notebook_alumno.ipynb`, `workbook.md`, `utils.py`, `data/productos.db` (se regenera con seed 42 al correr el setup; 5.000 eventos, 100 productos). |
| **Costo estimado** | Por alumno, una pasada: 1 (pedir_json) + 1 (V1) + 1 (papel) + 1 (externo) + 2 (workflow) + 4 (dos preguntas extra) = **10 llamadas**, cortas (200–600 tokens de salida). Muy barato comparado con el lab 01. |
| **Se evalúa** | No (ungraded en el original). Se puede pedir como entregable el notebook corrido con las dos preguntas extra y una oración de conclusión por cada una. |

## Secuencia sugerida (75 min)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–5 | Quiz. Las preguntas 1 y 2 repasan el lab 01. La 5 es la que planta el caso guía: dejar que discutan el signo. | Todos |
| 5–15 | Teoría: feedback externo vs. relectura. Analogía: releer el código vs. correr los tests. Dibujar el flujo. | Profesor |
| 15–25 | Correr el setup y la celda de la base. **Explicar el modelo de eventos en el pizarrón** con el producto 1: alta +20, venta -3, reposición +10, venta -5, stock = 22. Preguntar: "¿cómo calculo lo vendido en dinero?". Que lleguen solos a `-qty_delta * unit_price`. | Profesor |
| 25–30 | Celda resuelta `pedir_json`. Mostrar `utils.extraer_json` con un JSON envuelto en fences. Decir por qué levanta `ValueError` en vez de devolver algo por defecto. | Profesor |
| 30–40 | Huecos 1–2, `generar_sql`. Ejecutar V1. Pedir a tres alumnos que lean su `total_sales`. Casi todos negativos. | Alumnos |
| 40–50 | Huecos 3–4, `refinar_sql` (en papel). Leer feedbacks: la mayoría dice "correcta". Preguntar por qué el modelo no puede saberlo. | Alumnos |
| 50–60 | Huecos 5–7, `refinar_sql_con_feedback`. Antes: "¿qué le falta ver al modelo?". Mostrar `df.to_markdown()` en una celda aparte para que vean el texto que viaja. | Alumnos |
| 60–70 | Huecos 8–10, `correr_workflow_sql`. Insistir en `cambio = not misma_sql(...)`: el título verde/rojo sale de una comparación, no de un string fijo. | Alumnos |
| 70–75 | Preguntas extra (stock por categoría, unidades por marca). Cierre: "¿qué error no se vería mal en la tabla?" (puente a límites de la reflexión y al lab 03). | Todos |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

**En vivo (profesor):**
- Modelo de eventos en el pizarrón. Es el concepto que más cuesta y sin él el lab se
  reduce a "el modelo se equivocó en un signo".
- `pedir_json` y una demostración de `extraer_json` con una respuesta mal formateada.
- Mostrar `df_v1.to_markdown(index=False)` como texto plano antes del hueco 5.

**Los alumnos solos:**
- Los prompts de las tres funciones (cada uno tiene que decidir qué le muestra al
  modelo).
- Las preguntas extra. Que anoten en una celda markdown qué pasó con cada una.

## Dónde se traban (y qué decir)

1. **Llaves del JSON en el f-string.** Escriben `{"feedback": ...}` dentro de un
   f-string y Python lo interpreta como expresión. Síntoma: `NameError` o
   `SyntaxError: f-string: expecting '}'`. Decir: "en un f-string, la llave literal se
   escribe doble". Mostrar `{{` y `}}` en pantalla.
2. **Devuelven la V1 cuando el parseo falla.** Es el reflejo de "que no se rompa".
   Decir: "si el modelo no respondió lo que pediste, el problema está en el prompt;
   ocultarlo no lo arregla". Contar que el original hacía exactamente eso y mostraba
   V2 = V1 con un título que decía "mejorado".
3. **Olvidan `limpiar_sql`.** El SQL llega con ```sql y SQLite falla con
   `near "```"`. Mostrar el DataFrame de error y que lo arreglen.
4. **No incluyen la tabla en el prompt.** En `refinar_sql_con_feedback` convierten el
   DataFrame pero se olvidan de inyectar `{resultado_texto}`. El resultado es igual a
   la variante "en papel". Preguntar: "¿cómo sabés que el modelo vio la tabla?"
   Respuesta: imprimí la instrucción.
5. **Confunden stock con ventas.** En la pregunta "stock actual por categoría" la V1
   suele filtrar `action = 'sale'`. Buen momento para volver al pizarrón.
6. **Creen que `temperature=0` hace al modelo determinista.** Aclarar: reduce la
   variación, no la elimina; por eso comparamos con `misma_sql` en vez de asumir.
7. **La variante "en papel" ya corrige el signo.** Pasa en una de cada tres o cuatro
   corridas con `gpt-4.1` porque el nombre `qty_delta` sugiere delta. No es un
   fracaso del lab: por eso el notebook compara de verdad. Redirigir a las preguntas
   extra, donde la trampa es más opaca.

## Respuestas del quiz de apertura

1. **b.** Repaso: sin la crítica, la revisión es a ciegas.
2. **b.** La forma del SDK (aisuite imita a OpenAI).
3. **b.** El signo es una convención de los datos, invisible en el texto de la consulta. Las otras dos sí se ven leyendo.
4. **b.** Evidencia concreta. Es la idea central del lab.
5. **b.** Cantidad negativa por precio positivo da negativo. Pedir que lo verifiquen con la celda "Eventos por tipo".

## Soluciones de la extensión opcional (esbozo)

- **Documentar la convención.** `schema += "\nNota: qty_delta es negativo en las ventas."`.
  La V1 suele salir bien de entrada. Conclusión para discutir: documentar el schema
  es más barato que reflexionar, pero no cubre preguntas que el que documentó no
  previó (precio actual = último evento, por ejemplo).
- **Dos rondas.** Envolver los pasos 2–3 de `correr_workflow_sql` en un `for` con
  tope de 2 y cortar cuando `misma_sql` dé True. Lo habitual: la segunda ronda no
  cambia nada o cambia solo alias.
- **Modelo barato para reflexionar.** Con `gpt-4.1-mini` el signo se detecta igual
  en la mayoría de las corridas (la evidencia es muy clara). Dónde se nota la
  diferencia: en "precio actual", donde el barato tiende a promediar.
- **Romper la V1.** `refinar_sql_con_feedback(pregunta, "SELECT colour FROM transactions", df_error, schema)`.
  El modelo lee `no such column: colour` y corrige a `color`. Mostrar que la tabla de
  error también es feedback externo.
- **Preguntas ambiguas.** Agregar al prompt de `generar_sql`: "Si la pregunta es
  ambigua, elegí la interpretación más común y explicala en un comentario SQL `--`".
  Discutir cuándo conviene preguntar al usuario en vez de asumir (M3).

## Rúbrica

El lab no se evalúa con nota. Si se pide entregable, criterio simple: notebook
corrido de punta a punta sin errores, las dos preguntas extra ejecutadas, y una celda
markdown con una oración por pregunta diciendo si la reflexión corrigió algo y qué.

## Diferencias con el lab original de DeepLearning.AI

El original es el ungraded lab "Improving SQL Generation with Reflection" (`M2_UGL_2`).

| Qué se cambió | Por qué |
|---|---|
| `extraer_json` robusto a fences y prosa, que **levanta `ValueError`** si no hay JSON | El original hacía `json.loads(content)` y, si fallaba, devolvía `refined_sql = sql_query` en silencio. Cuando `gpt-4.1` envolvía el JSON en ```json (frecuente), el notebook mostraba V2 = V1 con el título "Refined SQL". Nadie se enteraba. |
| Títulos fijos de "error" y "éxito" (con íconos) reemplazados por una comparación real (`utils.misma_sql`) y un estilo verde/rojo según `cambio` | El original decía "Does NOT fully answer" y "Fully answers" como texto fijo, independientemente de lo que hubiera pasado. En corridas donde la V1 ya estaba bien, el notebook mentía. |
| Las tres funciones y el workflow son huecos; se agregó la celda resuelta `pedir_json` | El original venía todo resuelto (ungraded). Para convertirlo en ejercicio hacía falta un molde que mostrara el patrón "pedir JSON y validar". |
| `temperature=0` en la reflexión con feedback | El original usaba `temperature=1.0` en `refine_sql_external_feedback` (y 0 en las otras dos) sin explicar por qué. Unificado en 0: queremos la corrección más probable. |
| Modelos por parámetro (`AI_CHEAP` para generar, `AI_STRONG` para reflexionar), nunca hardcodeados; se sacaron `gpt-4o` y `gpt-3.5-turbo` de las sugerencias | Convención del material. |
| `ejecutar_sql` devuelve un DataFrame de error en vez de cortar; `limpiar_sql` separado y reutilizable | El original ya devolvía el error como DataFrame; se mantuvo y se explicitó que es feedback útil. `limpiar_sql` se expuso para que el alumno lo llame en `generar_sql`. |
| Base en `data/productos.db` con `seed` como parámetro y `mkdir` del directorio | El original la creaba en el cwd como `products.db`; con Jupyter abierto desde otra carpeta aparecía en lugares inesperados. |
| Explicación del modelo de eventos con tabla y ejemplo numérico; las fórmulas de stock, ventas y precio actual explícitas | El original tenía una caja de "schema overview" pero no explicaba cómo derivar cada métrica, que es justo donde el modelo se equivoca. |
| Preguntas extra con la trampa anotada | El original solo tenía el caso guía. |
| Prompts, pregunta guía y textos en español; nombres de columnas en inglés con nota | Convención del material; la base se conserva del original. |
| Se agregaron quiz, workbook, extensión opcional y esta guía | Convenciones del material. |

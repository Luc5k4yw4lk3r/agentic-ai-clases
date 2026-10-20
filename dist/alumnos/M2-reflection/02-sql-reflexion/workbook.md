# SQL con reflexión: de la pregunta en castellano a la consulta correcta

Material de acompañamiento del notebook `notebook_alumno.ipynb`. Leé las secciones 1
y 2 antes de la clase; tené la 4 a mano mientras trabajás.

## Antes de empezar (quiz de 5 preguntas)

1. (Repaso) En el lab anterior, ¿qué recibía `revisar_borrador` para poder mejorar el ensayo?
   a) Solo la consigna. b) El borrador y la crítica. c) El nombre del modelo.
2. (Repaso) ¿Dónde está el texto de la respuesta en el objeto que devuelve `client.chat.completions.create`?
   a) `response.text`. b) `response.choices[0].message.content`. c) `response.content`.
3. Un LLM revisa una consulta SQL leyendo solo el texto de la consulta y dice "está bien". ¿Qué tipo de error **no** puede detectar así?
   a) Un nombre de columna mal escrito. b) Un error de signo en los datos (por ejemplo, ventas guardadas como cantidades negativas). c) Un `SELECT` sin `FROM`.
4. ¿Qué le aporta al modelo ver el **resultado** de ejecutar la consulta, además del SQL?
   a) Nada, el SQL ya lo dice todo. b) Evidencia concreta: si el total de ventas es negativo, algo está mal aunque la consulta "se vea bien". c) Solo sirve para ahorrar tokens.
5. SQL: en una tabla donde cada venta se guarda con `qty_delta = -3` (tres unidades que salieron), ¿cuánto da `SUM(qty_delta * unit_price)` para las ventas?
   a) Un número positivo (el total vendido). b) Un número negativo. c) Cero.

## 1. Teoría breve

### Para qué: feedback externo

En el lab 01 el crítico leía un texto y opinaba. Para un ensayo no hay mucho más que
hacer. Pero cuando el modelo genera algo **ejecutable**, tenemos una fuente de verdad
mejor que su opinión: ejecutarlo y mirar el resultado. A eso lo llamamos **feedback
externo**: información que no sale del modelo sino del mundo (una base de datos, un
intérprete, un test, un usuario).

### Por qué así

El modelo conoce el **schema** (nombres y tipos de columnas) pero no los **datos**.
Si la base tiene una convención como "las ventas se guardan con cantidad negativa",
eso no está en el schema. El modelo no puede adivinarlo; puede, a lo sumo,
sospecharlo por el nombre `qty_delta`. En cambio, si ve que el total de ventas da
`-190571.46`, tiene una evidencia inequívoca de que algo está mal.

Dos variantes que vamos a comparar con el mismo caso:

| | Reflexión "en papel" | Reflexión con feedback externo |
|---|---|---|
| El modelo ve | pregunta + SQL + schema | lo mismo + **la tabla resultado** |
| Atrapa | sintaxis, columnas mal escritas, lógica evidente | además: signos, magnitudes absurdas, filtros que faltan, errores de SQLite |
| Costo | 1 llamada | 1 llamada + 1 ejecución (gratis) |

### El modelo de datos: eventos

La base tiene una sola tabla, `transactions`. Cada fila es un **evento**, no un estado:

| action | qué representa | qty_delta | unit_price |
|---|---|---|---|
| `insert` | alta del producto con stock inicial | positivo | precio inicial |
| `restock` | reposición | positivo | NULL |
| `sale` | venta | **negativo** | precio al momento |
| `price_update` | cambio de precio | 0 | nuevo precio |

Esto se llama *event sourcing*. No hay columna "stock" ni "ventas": se derivan.

- Stock actual de un producto: `SUM(qty_delta)` sobre todos sus eventos.
- Ventas en dinero: `SUM(-qty_delta * unit_price)` **solo** en filas `action = 'sale'`.
- Precio actual: el `unit_price` del último evento que tenga precio (no el promedio).

El signo negativo de las ventas es la trampa del lab.

### Pedir JSON y validarlo

Las funciones de reflexión devuelven dos cosas (feedback y SQL). Lo cómodo es pedir
un JSON:

```json
{"feedback": "<1 a 3 oraciones>", "sql_refinado": "<SQL final>"}
```

Reglas: pedí **solo** el JSON con los nombres exactos; después, **parseá y validá**.
`utils.extraer_json` tolera que el modelo envuelva el JSON en ```json ... ``` o le
agregue prosa, y levanta `ValueError` si no hay JSON. Vos tenés que verificar que los
dos campos existan. Nunca un `except` que devuelva la SQL original "por si acaso": eso
es exactamente el bug que tenía el lab original (mostraba V2 = V1 como si fuera una
mejora).

## 2. Ejemplo resuelto

La celda `pedir_json` está completa y es el molde de las dos funciones de reflexión:

```python
def pedir_json(instruccion: str, model: str = AI_STRONG) -> dict:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruccion}],
        temperature=0,
    )
    contenido = response.choices[0].message.content
    return utils.extraer_json(contenido)
```

Y así se ve el caso guía de punta a punta (*ejemplo ilustrativo, varía entre corridas*):

```
Pregunta: ¿Qué color de producto tiene las mayores ventas totales en dinero?

SQL V1:
SELECT color, SUM(qty_delta * unit_price) AS total_sales
FROM transactions WHERE action = 'sale'
GROUP BY color ORDER BY total_sales DESC LIMIT 1;

Resultado de V1:
| color | total_sales |
| blue  | -190571.46  |          <- negativo: imposible para "ventas"

Feedback (en papel):   "La consulta filtra ventas y agrupa por color; es correcta."
SQL V2 (en papel):     igual a V1          -> cambió: False

Feedback (con feedback externo):
  "El total es negativo porque qty_delta es negativo en las ventas.
   Invierto el signo para obtener el monto vendido."
SQL V2 (con feedback externo):
SELECT color, SUM(-qty_delta * unit_price) AS total_sales
FROM transactions WHERE action = 'sale'
GROUP BY color ORDER BY total_sales DESC LIMIT 1;  -> cambió: True

Resultado de V2:
| color | total_sales |
| white | 358315.09   |
```

Fijate que el color ganador **cambia** (de `blue` a `white`): con el signo invertido,
el "mayor" pasa a ser el que antes era el "menor". No era solo un signo cosmético.

## 3. Práctica graduada

### Nivel base (se corresponde con los huecos del notebook)

1. **`generar_sql(pregunta, schema, model) -> str`** (2 huecos). Escribí la instrucción
   (rol de asistente SQL para SQLite, schema, pregunta, "solo el SQL") y hacé la llamada
   con `temperature=0`. Pasá la respuesta por `utils.limpiar_sql` antes de devolverla.
   Ejecutá la V1 y anotá: ¿el total es negativo?
2. **`refinar_sql(pregunta, sql, schema, model) -> tuple[str, str]`** (2 huecos).
   Instrucción que pida evaluar y devolver el JSON con `feedback` y `sql_refinado`.
   Reusá `pedir_json`. Validá que los dos campos estén y que `sql_refinado` no esté
   vacío; si no, `ValueError`. Mirá la comparación `misma_sql(V1, V2)`.
3. **`refinar_sql_con_feedback(pregunta, sql, df_resultado, schema, model)`** (3 huecos).
   Igual que la anterior, pero antes convertí `df_resultado` a texto con
   `to_markdown(index=False)` e incluilo en la instrucción. Pedile explícitamente al
   modelo que mire signos, magnitudes y filtros, y que si hay una columna `error` la
   consulta falló.
4. **`correr_workflow_sql(db_path, pregunta, model_generacion, model_reflexion)`**
   (3 huecos). Encadená: schema → V1 → ejecutar → reflexión con feedback → V2 →
   ejecutar → `cambio = not misma_sql(V1, V2)`. Devolvé el dict con todas las piezas.
5. Corré las preguntas extra de la sección 8 y anotá, para cada una, si la V1 cayó en
   la trampa y si la reflexión la sacó.

### Extensión opcional (para los que terminan antes o para la casa)

- **Documentar la convención.** Agregá al texto del schema una línea: "qty_delta es
  negativo en las ventas y positivo en reposiciones". Corré la V1 de nuevo. Si ahora
  sale bien de entrada, ¿la reflexión se volvió inútil? Pensá en las otras preguntas.
- **Dos rondas.** Si `cambio` es True, ejecutá la V2 y reflexioná otra vez. Medí
  cuántas veces la V3 difiere de la V2. ¿Converge?
- **Modelo barato para reflexionar.** `model_reflexion=AI_CHEAP`. ¿Detecta el signo?
  ¿Y con `model_generacion=AI_STRONG, model_reflexion=AI_CHEAP`?
- **Romper la V1.** Pasale a `refinar_sql_con_feedback` una SQL con una columna
  inventada (`SELECT colour ...`). El DataFrame va a tener una columna `error`. ¿El
  modelo la usa para corregir?
- **Preguntas ambiguas.** "¿Cuál es el producto más vendido?" puede ser por unidades o
  por dinero. ¿Qué elige el modelo? ¿La reflexión lo nota? ¿Cómo cambiarías el prompt
  para que pregunte en vez de asumir?

## 4. Troubleshooting de más a menos frecuente

| Síntoma | Causa | Arreglo |
|---|---|---|
| `ValueError: No pude extraer un objeto JSON...` | El modelo respondió con prosa o con el SQL suelto en vez del JSON | Revisá que la instrucción termine con "Respondé únicamente con un JSON con exactamente estos dos campos" y que las llaves del ejemplo estén dobladas en el f-string (`{{` y `}}`). |
| `ValueError: El JSON del modelo no tiene los campos...` | El modelo usó otros nombres (`"query"`, `"sql"`) | Escribí los nombres exactos en el prompt, entre comillas. Es tu validación funcionando: no la saques. |
| `KeyError` o `NameError` dentro del f-string del prompt | Olvidaste doblar las llaves del JSON de ejemplo, o usás una variable que no existe | En un f-string, `{` literal se escribe `{{`. |
| El resultado de V1 es un DataFrame con una columna `error` | El SQL tiene un error de SQLite (columna inexistente, comillas) | Es información: pasá ese DataFrame a `refinar_sql_con_feedback` y mirá si el modelo lo arregla. Si el error es `near "```"`, te faltó `utils.limpiar_sql`. |
| `ImportError: Missing optional dependency 'tabulate'` | `to_markdown` necesita `tabulate` | `pip install tabulate` (está en `requirements.txt` de la raíz). |
| La V2 "en papel" ya corrigió el signo y no se ve la diferencia con la variante externa | El modelo lo sospechó por el nombre `qty_delta`; pasa en algunas corridas | No es un error. Probá "¿Cuál es el stock actual de cada categoría?" o "¿Qué marca vendió más unidades?" para ver una trampa que la lectura sola no atrapa. |
| `cambio` da True pero las consultas se ven iguales | Diferencias de espacios, mayúsculas o `;` final | `utils.misma_sql` ya normaliza eso. Si igual da True, hay un cambio real: mirá alias o `LIMIT`. |
| `sqlite3.OperationalError: no such table: transactions` | Se abrió el notebook desde otra carpeta y `data/productos.db` quedó en otro lado | Corré la celda de `crear_db_transacciones` de nuevo; crea la base donde apunte `DB_PATH`. |

## 5. Para cerrar

### Tres preguntas de reflexión

1. El feedback externo acá es "gratis" (ejecutar un `SELECT` sobre SQLite). ¿Qué pasa
   con el patrón cuando ejecutar tiene costo o riesgo (un `DELETE`, una llamada a una
   API paga, enviar un mail)? ¿Qué pondrías entre la generación y la ejecución?
2. La reflexión corrigió el signo porque el total negativo "se ve mal". ¿Qué error
   **no** se vería mal en la tabla y por lo tanto la reflexión con feedback tampoco
   atraparía? (Pista: un filtro de fechas que falta devuelve números razonables.)
3. ¿Qué parte del problema se resuelve mejor documentando el schema y qué parte
   necesita reflexión de verdad?

### Checklist de autoevaluación

- [ ] Puedo explicar la diferencia entre reflexión "en papel" y con feedback externo
      con el ejemplo del signo.
- [ ] Mis funciones de reflexión piden JSON con nombres exactos y **validan** los
      campos; si falta algo, levantan `ValueError` con mensaje en español.
- [ ] Sé qué es `df.to_markdown(index=False)` y para qué sirve en un prompt.
- [ ] `correr_workflow_sql` devuelve `cambio` calculado con `misma_sql`, no asumido.
- [ ] Puedo explicar el modelo de eventos: por qué el stock es `SUM(qty_delta)` y las
      ventas son `SUM(-qty_delta * unit_price)` filtrando `action = 'sale'`.
- [ ] Corrí al menos dos preguntas extra y anoté si la V1 cayó en la trampa.

# Atención al cliente con un plan de tools

**Módulo 5 · Lab 01.** Planner → Reflector → Executor → Explicador para una tienda de
anteojos de sol. El LLM escribe un plan en JSON que solo puede usar tools de un catálogo
cerrado; un executor en Python lo corre con validaciones y frena si algo no cierra.

## Antes de empezar (quiz de 5 preguntas)

Respondé antes de leer la teoría. Las respuestas están en el notebook del profesor.

1. (Repaso M4) Medir la calidad de la búsqueda web sin generar el ensayo completo es una
   evaluación: a) end-to-end  b) a nivel de componente  c) subjetiva con LLM como juez
2. (Repaso M4) "Proporción de URLs de dominios preferidos" es una métrica:
   a) subjetiva  b) objetiva con ground truth por ejemplo  c) imposible de calcular con código
3. (Nuevo) ¿Qué ganamos si el plan solo puede usar nombres de tools de un catálogo?
   a) velocidad  b) cada paso es auditable y acotado a lo que las tools permiten  c) no hace falta validar
4. (Nuevo) `"price_from": "context.prod.item.price"` significa:
   a) buscar el precio en internet  b) tomar el valor que un paso anterior guardó bajo
   `result_key: "prod"`  c) es un comentario
5. (Base) Si hacés `inv2 = inventory_df.copy()` y modificás `inv2`, ¿cambia `inventory_df`?
   a) sí  b) no  c) depende del tamaño

## 1. Teoría breve

### Para qué: separar "pensar" de "hacer"

En los módulos anteriores un solo agente hacía todo: razonaba, llamaba tools, escribía la
respuesta. Acá dividimos el trabajo en **roles**, cada uno con una tarea chica y clara:

| Rol | Quién | Entrada | Salida |
|---|---|---|---|
| Planner | LLM barato | pedido del cliente | plan JSON |
| Reflector | LLM fuerte | pedido + plan | crítica + plan revisado |
| Executor | **código Python, sin LLM** | plan + DataFrames | reporte + DataFrames nuevos |
| Explicador | LLM barato | pedido + reporte fallido | 2 o 3 frases para el cliente |

El punto central: **el LLM nunca toca los datos.** Propone un plan; el executor decide si
cada paso es válido y lo ejecuta con funciones que nosotros escribimos y probamos.

### Por qué así: un plan es un dato

Un plan JSON se puede imprimir, guardar, comparar, revisar con otro modelo y ejecutar
después. Un agente que "hace cosas mientras piensa" no te da esa oportunidad. Además, como
el plan solo puede nombrar tools del catálogo (`tools.TOOL_REGISTRY`), el peor caso es un
`ValueError: Tool desconocida`, no un `DROP TABLE`.

### El esquema `*_from` y el contexto

Durante la ejecución existe un dict `ctx`. Cada tool guarda su resultado en
`ctx[result_key]`. Un paso posterior puede pedir un valor de ahí con un arg que termine en
`_from` y una ruta `context.a.b.c`:

```text
paso 1:  get_inventory_data(product_name="Sport")  →  ctx["prod"] = {"rows": ..., "match_count": 1,
                                                                       "item": {"item_id": "SG004", "price": 144, ...}}

paso 2 pide:  {"qty": 2, "price_from": "context.prod.item.price"}
                                          └──────┬──────┘
             resolve_args recorre  ctx → "prod" → "item" → "price"  = 144
             y quita el sufijo:   {"qty": 2, "price": 144}

paso 2 corre: compute_refund(qty=2, price=144)  →  ctx["refund"] = {"amount": -288.0}
```

Si la ruta no existe (el producto no se encontró y `item` es `null`), `resolve_args` levanta
`ValueError` con la parte exacta que falló. Nada de `None` silencioso.

### Ejemplo práctico: por qué el estado no cambia solo

Las tools de escritura (`update_inventory`, `append_transaction`) devuelven un DataFrame
**nuevo**. El executor trabaja sobre **copias**. Al final te devuelve
`reporte["updated_frames"]`. Si no hacés

```python
inventory_df = reporte["updated_frames"]["inventory_df"]
transaction_df = reporte["updated_frames"]["transaction_df"]
```

la tienda sigue igual que antes. Es incómodo a propósito: adoptar un cambio es una decisión
explícita, no un efecto secundario.

## 2. Ejemplo resuelto

Pedido: **"Quiero devolver dos anteojos Sport"**. Un plan correcto tiene 4 pasos:

```json
{
  "reasoning": "Devolver 2 Sport: buscar, calcular reintegro negativo, sumar stock, registrar.",
  "steps": [
    {"step_number": 1, "description": "Buscar el producto 'Sport'",
     "tools": [{"use": "get_inventory_data", "args": {"product_name": "Sport"}, "result_key": "prod"}],
     "validations": [{"name": "producto_encontrado", "use_tool": "assert_true", "args": {"value_from": "context.prod.item"}}]},
    {"step_number": 2, "description": "Calcular el reintegro",
     "tools": [{"use": "compute_refund", "args": {"qty": 2, "price_from": "context.prod.item.price"}, "result_key": "refund"}],
     "validations": []},
    {"step_number": 3, "description": "Sumar 2 al stock",
     "tools": [{"use": "update_inventory", "args": {"item_id_from": "context.prod.item.item_id", "delta": 2}, "result_key": "inv_after"}],
     "validations": [{"name": "stock_no_negativo", "use_tool": "assert_nonnegative_stock", "args": {"item_id_from": "context.prod.item.item_id"}}]},
    {"step_number": 4, "description": "Registrar la devolución",
     "tools": [{"use": "append_transaction", "args": {"customer_name": "CLIENTE_MOSTRADOR", "summary": "Devolución de 2 anteojos Sport", "amount_from": "context.refund.amount"}, "result_key": "txn"}],
     "validations": [{"name": "transaccion_creada", "use_tool": "assert_true", "args": {"value_from": "context.txn.transaction.transaction_id"}}]}
  ]
}
```

Salida de `utils.resumen_reporte(ejecutar_plan(plan, inventory_df, transaction_df))`
(esta sí es determinística, porque no hay LLM):

```text
Estado general: OK
  Paso 1: Buscar el producto 'Sport'  [ok]
      tools: ['prod']
      validación 'producto_encontrado': ok
      validación 'stock_no_negativo (executor)': ok
  Paso 2: Calcular el reintegro  [ok]
      tools: ['refund']
      validación 'stock_no_negativo (executor)': ok
  Paso 3: Sumar 2 al stock  [ok]
      tools: ['inv_after']
      validación 'stock_no_negativo': ok {'qty': 13}
      validación 'stock_no_negativo (executor)': ok
  Paso 4: Registrar la devolución  [ok]
      tools: ['txn']
      validación 'transaccion_creada': ok
      validación 'stock_no_negativo (executor)': ok
```

Y en `updated_frames`: Sport pasa de 11 a 13, la caja suma una fila `TXN002` por -288.0 y el
saldo baja de 500.0 a 212.0. El `inventory_df` original sigue en 11 hasta que lo reasignes.

Qué pasa con el mismo pedido pero **comprando 5 Mystique** (hay 3): el paso 3 deja el stock
en -2, la validación `stock_no_negativo` da `ok: False`, el executor marca el paso como
fallido, agrega `aborted: True, abort_step: 3` y **no llega al paso 4**: la caja no se toca.

## 3. Práctica graduada

### Nivel base (uno a uno con los huecos del notebook)

1. **Executor, hueco acotado.** En `ejecutar_plan`, completá el "Paso 2": correr cada
   validación del plan con `tools.run_tool_validation(v, ctx)`, agregar
   `validar_stock_no_negativo(ctx)` a la lista y calcular `paso_ok` (sin error de tool y
   todas las validaciones en `ok`). Probalo con `EJEMPLO_PLAN` (tiene que pasar) y con
   `PLAN_MYSTIQUE_SIN_VALIDAR` (tiene que frenar en el paso 2 aunque el plan no pida
   ninguna validación).
2. **Planner, llamada.** En `generar_plan`, armá los mensajes (system corto que pida JSON;
   user con `especificacion_planner(catalogo)` más el pedido) y llamá al modelo con
   `response_format={"type": "json_object"}`.
3. **Planner, validación.** Convertí el texto con `utils.parsear_json` y levantá
   `ValueError` si `steps` no es una lista no vacía. Probá qué pasa si le pasás un pedido
   vacío.
4. **Reflector, llamada.** En `reflexionar_plan`, pedí un JSON con `critica` y
   `plan_revisado`, pasando la especificación, el pedido y el borrador serializado con
   `json.dumps`.
5. **Reflector, fallback.** Si `plan_revisado` no es un dict con `steps`, avisá con `print`
   y devolvé el borrador original. Probalo con `BORRADOR_CON_ERRORES`: la crítica tiene que
   mencionar `quantity`/`qty` o la validación que falta.
6. **Explicador.** En `explicar_error`, llamá al modelo barato con el pedido y el reporte
   (sin `updated_frames`) y devolvé el texto. Probalo con `reporte_fallido`.

Cuando termines, corré en una celda:

```python
from tests import run_all
run_all(ejecutar_plan)
```

### Extensión opcional

- **Nueva tool.** Agregá `get_low_stock(con, threshold)` a `tools.py` (función +
  `TOOL_REGISTRY` + `ARGS_OBLIGATORIOS` + `RECURSOS_COMPARTIDOS` + una entrada en
  `CATALOGO_TOOLS`). Pedile al planner "¿qué modelos están por agotarse?" y mirá si la usa.
- **Medir al reflector.** Corré 5 pedidos distintos y contá en cuántos el `plan_revisado`
  difiere del borrador (`json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)`).
  ¿Justifica una llamada al modelo fuerte por pedido?
- **Pedido ambiguo.** Probá "quiero unos anteojos" y "¿tienen algo barato?". Ajustá
  `REGLAS_PLANNER` para que en esos casos el plan tenga un solo paso de lectura y un
  `reasoning` que diga qué falta preguntar.
- **Sin reflector.** Comentá la llamada al reflector en `atender_pedido` y repetí los tres
  casos. ¿Cambia algo? ¿Con qué frecuencia?

## 4. Troubleshooting de más a menos frecuente

| Síntoma | Causa | Arreglo |
|---|---|---|
| `ValueError: La referencia 'context.prod.item.price' no se puede resolver: 'context.prod.item' no tiene la clave...` | El producto no se encontró (`item` es `None`) o el paso anterior usó otro `result_key` | Mirá el reporte: la validación `producto_encontrado` del paso 1 tiene que haber fallado antes. Si el planner escribió el nombre mal, el reflector debería corregirlo. |
| `ValueError: Tool desconocida: 'lookup_product'` | El modelo inventó una tool (pasaba en el original, que tenía alias) | Está bien que falle. Revisá que el prompt incluya `tools.CATALOGO_TOOLS` completo y el ejemplo. |
| `ValueError: A la tool 'compute_total' le faltan args obligatorios: ['qty']` | El plan usó `quantity` y `canonicalize_args` no lo tradujo, o faltó el arg | Agregá el alias en `canonicalize_args` o dejá que el reflector lo corrija. |
| El inventario "no cambia" después de un pedido exitoso | No reasignaste `inventory_df = reporte["updated_frames"]["inventory_df"]` | Es a propósito. Reasigná en la celda. |
| `ValueError: El planner devolvió un JSON sin una lista 'steps' válida` | El modelo devolvió `{"plan": {...}}` u otra forma | Mirá qué claves vinieron (el mensaje las lista). Reforzá en el prompt "las claves son exactamente reasoning y steps". |
| `AssertionError: Falta OPENAI_API_KEY` | No hay `.env` en la raíz del material | `cp .env.example .env` y completá la clave. |

## 5. Para cerrar

**Tres preguntas de reflexión**

1. El executor tiene un chequeo de stock propio aunque el plan ya pida
   `assert_nonnegative_stock`. ¿Es redundante? ¿Qué pasaría si confiáramos solo en el
   planner?
2. ¿Qué tipo de pedidos NO puede atender este sistema con el catálogo actual? Nombrá dos y
   decí qué tool habría que agregar.
3. Si el planner fuera perfecto, ¿seguiría teniendo sentido el reflector? ¿Y el executor?

**Checklist de autoevaluación**

- [ ] Puedo explicar qué hace cada uno de los cuatro roles y cuál NO usa LLM.
- [ ] Puedo seguir a mano una referencia `context.a.b.c` hasta su valor.
- [ ] Sé por qué `inventory_df` no cambia hasta que lo reasigno.
- [ ] Mi `ejecutar_plan` frena en el paso correcto con 5 Mystique y `run_all` pasa.
- [ ] Mi `generar_plan` levanta `ValueError` legible si el JSON no tiene `steps`.

# Agente de investigación con function calling "a mano"

Material de acompañamiento del lab 02 del módulo 3. Se lee antes, durante y
después del notebook `notebook_alumno.ipynb`. El notebook tiene el código
guiado; esto explica y propone práctica.

## Antes de empezar (quiz de 5 preguntas)

Respondé antes de leer la teoría. Las respuestas se discuten en clase.

1. Ayer, con `aisuite`, ¿qué activaba el loop de tool use?
   a) `tools=[...]` solo.   b) El parámetro `max_turns`.   c) Un docstring que dijera "loop".
2. En el experimento de la tool que faltaba, ¿por qué el agente no pudo borrar el mail?
   a) El modelo no sabía que existía el concepto de borrar.
   b) `borrar_email` no estaba en la lista de tools; el modelo solo puede pedir lo que le ofrecés.
   c) El servidor rechazó la llamada.
3. Con el SDK de OpenAI directo, cuando el modelo quiere usar una tool, ¿qué devuelve?
   a) El resultado de la tool, ya ejecutada.
   b) Un mensaje con `tool_calls`: nombre de la función y argumentos como string JSON, sin ejecutar nada.
   c) Un error, porque el SDK no soporta tools.
4. ¿Qué tiene que tener el mensaje que le devolvés al modelo con el resultado de una tool?
   a) `role: "user"` y el resultado como texto.
   b) `role: "tool"`, el `tool_call_id` de la llamada que responde y el resultado en `content`.
   c) `role: "assistant"` con el resultado.
5. `json.loads('{"query": "RAG", "max_results": 3}')` devuelve:
   a) Un string.   b) Un dict de Python.   c) Una lista.

## 1. Teoría breve

### 1.1 Por qué sacar a `aisuite` del medio

**Para qué.** Ayer `aisuite` hizo cuatro cosas por vos: armó los schemas desde
los docstrings, llamó al modelo, ejecutó las tools que pidió y le devolvió los
resultados en loop. Funciona, pero cuando algo falla (un argumento mal
parseado, un `tool_call_id` que no coincide, un loop que no termina) necesitás
saber qué hay abajo. Y lo que hay abajo es siempre lo mismo, en cualquier
proveedor y en cualquier framework: el protocolo de **function calling**.

**Por qué así.** El protocolo tiene cuatro pasos y ningún truco:

```
1. Mandás messages + tools (lista de schemas JSON).
2. El modelo responde con message.tool_calls = [ {id, function: {name, arguments}} ].
   "arguments" es un STRING con JSON adentro. Nadie ejecutó nada.
3. Vos ejecutás la función y agregás a messages:
      el mensaje del modelo (con sus tool_calls)
      + {"role": "tool", "tool_call_id": id, "content": resultado_como_string}
4. Volvés a llamar. Texto → terminaste. Más tool_calls → volvés al paso 3.
```

**Ejemplo práctico.** Pedís "tres papers sobre RAG" con `tools=[arxiv_tool_def]`.
El modelo devuelve `content=None` y un `tool_call` con
`name="arxiv_search_tool"`, `arguments='{"query": "retrieval-augmented generation", "max_results": 3}'`.
Vos hacés `json.loads`, llamás a `arxiv_search_tool(**args)`, serializás el
resultado con `json.dumps` y lo devolvés como mensaje `tool`. En la segunda
llamada el modelo ya tiene los papers y escribe el texto.

### 1.2 El schema a mano

Lo que ayer salía del docstring hoy lo escribís vos. La forma es fija:

```python
{
  "type": "function",
  "function": {
    "name": "wikipedia_search_tool",         # = la clave en tool_mapping
    "description": "Cuándo usar esta tool",  # lo que lee el modelo para decidir
    "parameters": {                          # JSON Schema
      "type": "object",
      "properties": {
        "query": {"type": "string", "description": "..."},
        "max_results": {"type": "integer", "description": "...", "default": 3},
      },
      "required": ["query"],                 # los que no tienen default
    },
  },
}
```

Tres errores frecuentes: olvidar `"type": "object"` en `parameters`; poner en
`required` un parámetro que tiene default (el modelo lo manda siempre, aunque no
haga falta); y que el `name` no coincida con la clave de `tool_mapping`
(`KeyError` al despachar).

### 1.3 El despacho y el loop

El modelo devuelve el nombre de la tool como string. Para ejecutarla necesitás
un dict nombre → función:

```python
tool_mapping = {"arxiv_search_tool": research_tools.arxiv_search_tool, ...}
resultado = tool_mapping[call.function.name](**json.loads(call.function.arguments))
```

El loop es un `for` de hasta `max_turns` vueltas con los tres pasos de la
sección 1.1. Dos reglas:

- **Siempre** agregá el mensaje del modelo a `messages` antes de los mensajes
  `tool`. La API exige que cada `tool` responda a un `tool_call` que esté en el
  mensaje `assistant` inmediatamente anterior.
- Si una tool falla (sin internet, API caída), no cortes el loop: devolvé
  `{"error": "..."}` como resultado. El modelo lee el error y decide (prueba
  otra tool, o escribe sin esa fuente).

### 1.4 El pipeline y lo que cuesta

Después del loop vienen dos pasos de M2: **reflexión** (criticar y reescribir,
en dos llamadas separadas, con `MODEL_STRONG`) y **formato** (a HTML, con
`MODEL_CHEAP`). Una corrida completa son entre 5 y 10 llamadas, y las de
reflexión llevan el informe entero adentro. Antes de correr algo, estimá
cuántas llamadas va a hacer.

### 1.5 Las tools de hoy

`research_tools.py` tiene tres funciones de búsqueda y sus schemas de
referencia: `arxiv_search_tool` (papers), `wikipedia_search_tool`
(definiciones; usa la API de MediaWiki con `requests`) y `tavily_search_tool`
(web general; sin `TAVILY_API_KEY` cae a Wikipedia y lo avisa en el campo
`source`). Las tres devuelven listas de dicts con `title`, `url`, `snippet`.

**Las queries van en inglés**: arXiv indexa casi todo en inglés y la Wikipedia
en inglés es mucho más completa que la de español. El informe lo pedimos en
español igual; el system prompt se lo dice al modelo.

## 2. Ejemplo resuelto

Las secciones 2.1 y 2.2 del notebook son una vuelta completa del loop a mano,
con los prints puestos para que veas cada pieza. Salida de 2.1 (*ejemplo
ilustrativo; varía entre corridas*):

```
content   : None
tool_calls: 1
  id       : call_9Xk2...
  name     : arxiv_search_tool
  arguments: '{"query":"retrieval-augmented generation","max_results":3}' <- es un string, hay que hacer json.loads
```

Y de 2.2:

```
Ejecuté arxiv_search_tool({'query': 'retrieval-augmented generation', 'max_results': 3}) -> 3 resultado(s)

tool_calls en la segunda respuesta: None

Respuesta final:
 Encontré tres papers recientes sobre RAG:
 1. ... (https://arxiv.org/abs/...)
```

Qué mirar:

- `content` es `None` en la primera respuesta. El modelo no habló: pidió.
- `arguments` tiene comillas alrededor: es un string. Sin `json.loads` no podés
  hacer `**args`.
- El `tool_call_id` del mensaje `tool` es el `call.id` de la primera respuesta.
- En la segunda respuesta `tool_calls` es `None`: eso es lo que corta el loop.

Esta es exactamente la estructura que vas a generalizar en `investigar_con_tools`.

## 3. Práctica graduada

### Nivel base (los huecos del notebook, en orden)

1. **`wikipedia_tool_def`** (sección 3). Copiá la forma de `arxiv_tool_def` y
   adaptala a `wikipedia_search_tool(query: str, max_results: int = 3, lang: str = "en")`.
   Pensá la `description`: ¿para qué sirve Wikipedia que arXiv no? Podés no
   exponer `lang`. Chequeá con `utils.comparar_schemas(...)` y con
   `run_all(wikipedia_tool_def)`.
2. **`investigar_con_tools`, paso 1** (sección 5). La llamada con
   `tools=TOOL_DEFS`; guardá `response.choices[0].message` en `msg` y agregalo a
   `messages`.
3. **Paso 2.** `if not msg.tool_calls: return msg.content`. Es la condición de
   corte; sin ella el loop sigue hasta `max_turns` aunque ya tenga la respuesta.
4. **Paso 3.** Un `for call in msg.tool_calls` con: `json.loads` de los
   argumentos, `tool_mapping[nombre](**args)` dentro de un `try/except` que
   convierta cualquier excepción en `{"error": ...}`, y el `append` del mensaje
   `tool` con `call.id`. Corré `run_all(investigar_con_tools)`: usa un cliente
   falso y no gasta llamadas.
5. **`reflexionar_y_reescribir`** (sección 6). Dos llamadas: la primera con
   `PROMPT_CRITICA.format(informe=...)`, la segunda con
   `PROMPT_REESCRITURA.format(informe=..., critica=...)`. Validá que ninguna
   venga vacía. Devolvé `{"critica": ..., "informe_revisado": ...}`.
6. **`convertir_a_html`** (sección 7). Una llamada con `PROMPT_HTML`, después
   `quitar_fences` (ya está escrita) y validar que haya `<` y `>`; si no,
   `ValueError`.

Después: correr el pipeline completo de la sección 8 **una vez**, abrir el HTML
que quedó en `informes/`, y anotar cuántas llamadas hizo.

### Extensión opcional (para los que terminan antes o para la casa)

1. **Sin Wikipedia.** Sacá `wikipedia_tool_def` de `TOOL_DEFS` y repetí el
   pedido de la sección 5. ¿De dónde saca las definiciones? ¿Usa Tavily (o su
   fallback)? ¿Cambia la cantidad de turnos?
2. **Traza completa.** Hacé que `investigar_con_tools` devuelva un dict con
   `informe` y `messages`, y escribí `mostrar_traza(messages)` como la de ayer.
   Diferencia con ayer: acá los mensajes del modelo son objetos del SDK y los
   `tool` son dicts que armaste vos, así que ya sabés qué forma tienen.
3. **Crítica con criterios.** Cambiá `PROMPT_CRITICA` para que devuelva JSON
   con tres puntajes de 1 a 5 (`fuentes`, `precision`, `claridad`) y un campo
   `comentarios`. Usá `response_format={"type": "json_object"}`, parseá con
   `json.loads` y validá las claves (con `ValueError` si falta alguna). Decidí
   una regla: si `fuentes < 3`, ¿volvés a llamar a `investigar_con_tools` con
   el pedido más específico?
4. **Tool sin parámetros.** `fecha_de_hoy() -> str` con su schema
   (`"properties": {}` y `"required": []`). Agregala y pedí "lo publicado este
   mes sobre X". ¿La usa? ¿La usa también cuando no hace falta? ¿Qué dice la
   `description` que la hace más o menos tentadora?

## 4. Troubleshooting de más a menos

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `AssertionError: Falta OPENAI_API_KEY` o `AuthenticationError` | No hay `.env` o el notebook no lo encuentra. | `cp .env.example .env` en la raíz del material y pegá la key. Reiniciá el kernel. |
| `requests.exceptions.ConnectionError` al probar `arxiv_search_tool` en la sección 1 | Sin internet, o una red que bloquea `export.arxiv.org`. | Probá la URL en el navegador. Si la red corporativa bloquea, usá los datos de celular. El loop igual sigue (devuelve `{"error": ...}` al modelo), pero el informe sale sin papers. |
| `openai.BadRequestError: ... messages with role 'tool' must be a response to a preceding message with 'tool_calls'` | Agregaste el mensaje `tool` sin agregar antes el mensaje del modelo, o el `tool_call_id` no es el `call.id`. | En el paso 1 hacé `messages.append(msg)` antes de ejecutar nada. En el paso 3 usá `call.id`, no un string inventado. |
| `KeyError: 'wikipedia_search_tool'` (o parecido) al ejecutar una tool | El `name` del schema no coincide con la clave de `tool_mapping`. | Compará los dos strings letra por letra. La celda de la sección 4 tiene un `assert` que lo detecta antes de gastar llamadas. |
| `TypeError: arxiv_search_tool() got an unexpected keyword argument 'lang'` | Expusiste en el schema un parámetro que la función no acepta (o al revés, con otro nombre). | Los nombres en `properties` tienen que ser exactamente los de la firma de la función. |
| `TypeError: string indices must be integers` o `**args` falla | Pasaste `call.function.arguments` sin `json.loads`. | `args = json.loads(call.function.arguments)` y después `funcion(**args)`. |
| `RuntimeError: El agente agotó los 8 turnos sin dar una respuesta final` | El modelo sigue pidiendo tools; pasa con pedidos muy abiertos o si una tool devuelve siempre vacío y el modelo reintenta. | Acotá el pedido ("al menos un paper y una definición" en vez de "todo lo que encuentres"). Mirá la traza impresa: si repite la misma query, agregá al system prompt "no repitas una búsqueda que ya hiciste". |
| El HTML se ve como texto plano con ```` ``` ```` arriba y abajo | El modelo envolvió el HTML en fences de markdown y no los quitaste. | `quitar_fences` antes de validar. Si el modelo pone otra cosa antes del HTML, ajustá `PROMPT_HTML` ("Respondé SOLO con el HTML"). |
| `reflexionar_y_reescribir` devuelve lo mismo en `critica` e `informe_revisado` | Hiciste una sola llamada pidiendo las dos cosas. | Dos llamadas. La segunda recibe el informe original **y** la crítica. `run_all(reflexionar_y_reescribir)` lo detecta. |
| La cuenta de la API subió más de lo que esperabas | Corriste el pipeline varias veces, o `max_turns` alto con un pedido abierto. | Cada corrida completa son 5 a 10 llamadas, la mitad al modelo fuerte con el informe adentro. Probá cada función con `run_all` (cliente falso) antes de la real; corré el pipeline una vez por tema. |

## 5. Para cerrar

Tres preguntas de reflexión:

1. ¿Qué hacía `aisuite` que vos tuviste que escribir hoy? ¿Qué parte te
   parece más propensa a errores si la escribís vos, y qué parte preferís
   controlar?
2. La tool `tavily_search_tool` cae a Wikipedia cuando no hay key y lo avisa en
   el resultado. ¿Qué pasaría si fallara en silencio devolviendo una lista
   vacía? ¿Y si lanzara una excepción que corta el loop?
3. El informe revisado no puede agregar fuentes nuevas (lo dice
   `PROMPT_REESCRITURA`). ¿Por qué esa restricción? ¿Qué riesgo evita?

Checklist de autoevaluación:

- [ ] Puedo escribir el schema de una tool nueva de memoria, con `required` bien puesto.
- [ ] Sé qué forma tiene un `tool_call` y por qué `arguments` hay que parsearlo.
- [ ] Mi loop pasa los cinco chequeos de `run_all(investigar_con_tools)`, incluido el de la tool que falla.
- [ ] Entiendo por qué el mensaje `tool` necesita el `tool_call_id` y qué pasa si no coincide.
- [ ] Mi reflexión son dos llamadas y la segunda recibe la crítica.
- [ ] Puedo estimar cuántas llamadas hace una corrida antes de lanzarla.

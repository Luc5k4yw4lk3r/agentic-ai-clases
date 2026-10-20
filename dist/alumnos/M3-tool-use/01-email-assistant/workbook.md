# Asistente de email con tools (aisuite)

Material de acompañamiento del lab 01 del módulo 3. Se lee antes, durante y
después del notebook `notebook_alumno.ipynb`. El notebook tiene el código
guiado; esto explica y propone práctica.

## Antes de empezar (quiz de 5 preguntas)

Respondé antes de leer la teoría. Las respuestas se discuten en clase.

1. En el patrón de reflexión del módulo anterior, ¿qué recibía la segunda llamada al modelo?
   a) El mismo prompt que la primera, para probar suerte otra vez.
   b) El borrador generado más una consigna de criticarlo.
   c) Solo la crítica, sin el borrador.
2. En M2, cuando el modelo generaba una consulta SQL, ¿qué hacíamos antes de confiar en ella?
   a) La ejecutábamos y validábamos el resultado (y si fallaba, el error volvía al modelo).
   b) La copiábamos tal cual al informe.
   c) Le pedíamos al modelo que prometiera que estaba bien.
3. Cuando el modelo "llama a una tool", ¿quién ejecuta la función?
   a) El modelo, en los servidores de OpenAI.
   b) Tu código (acá, `aisuite`), en tu máquina; el modelo solo pide la llamada.
   c) El servidor de email, que la recibe directo del modelo.
4. ¿De dónde saca `aisuite` la descripción de una tool para mostrársela al modelo?
   a) Solo del nombre de la función.
   b) De la firma (tipos y defaults) más el docstring.
   c) La escribe el modelo la primera vez que la usa.
5. En una API REST, ¿qué método HTTP corresponde a "marcar un mail como leído"?
   a) GET   b) PATCH   c) DELETE

## 1. Teoría breve

### 1.1 Qué es una tool

**Para qué.** Un LLM produce texto; nada más. Para que *haga* cosas en el mundo
(consultar una base, mandar un mail, buscar en la web) alguien tiene que
ejecutar código por él. Una **tool** es una función Python que vos ponés a
disposición del modelo. Él decide *cuándo* llamarla y *con qué argumentos*; tu
programa la ejecuta y le devuelve el resultado; el modelo sigue razonando con
esa información.

**Por qué así.** Separar "decidir" (el modelo) de "ejecutar" (tu código) tiene
dos ventajas: el modelo nunca tiene acceso directo a nada (vos controlás qué
funciones existen y qué hacen), y todo lo que pasa queda registrado en
mensajes que podés leer después.

**Ejemplo práctico.** Un pedido como *"fijate si tengo mails nuevos de la jefa y
respondele"* se convierte en:

```
usuario ─▶ modelo: "llamá a buscar_no_leidos_de(remitente='jefa@empresa.com')"
           tu código ejecuta la función ─▶ [ {id: 3, asunto: "Reporte trimestral", ...} ]
           modelo: "llamá a marcar_como_leido(email_id=3)"
           tu código ejecuta ─▶ {id: 3, leido: true}
           modelo: "llamá a enviar_email(destinatario='jefa@empresa.com', asunto=..., cuerpo=...)"
           tu código ejecuta ─▶ {id: 7, ...}
           modelo ─▶ usuario: "Encontré un mail de la jefa, lo marqué como leído y le respondí."
```

Cada flecha de ida y vuelta es un **turno**. Ese ciclo (razonar → actuar →
observar → repetir) es el **loop de tool use**.

### 1.2 Cómo las ve el modelo: el schema

El modelo no ve tu código. Ve un **schema JSON** por cada tool: nombre,
descripción y parámetros (nombre, tipo, descripción, si es obligatorio).
`aisuite` lo arma solo a partir de dos cosas:

- la **firma** de la función: nombres de parámetros, type hints (obligatorios,
  si falta uno lanza `TypeError`) y valores por defecto (un parámetro con
  default es opcional);
- el **docstring**: la primera línea es la descripción de la tool; las líneas
  bajo `Args:` son las descripciones de cada parámetro.

Por eso en este lab insistimos tanto con los docstrings: **el docstring es parte
del prompt**. Un docstring que dice solo "Busca." deja al modelo adivinando;
uno que dice "Busca emails que contengan el texto en el asunto, el cuerpo o el
remitente. No distingue mayúsculas. Usala para encontrar un mail por tema o por
remitente" le dice cuándo conviene usarla. Las buenas prácticas:

- primera línea imperativa y específica ("Marca un email como leído");
- una o dos líneas más diciendo *cuándo* usarla;
- en `Args:`, formato esperado y un ejemplo ("dirección exacta. Ej: `jefa@empresa.com`");
- en `Returns:`, qué estructura devuelve, para que el modelo sepa cómo encadenarla.

### 1.3 `aisuite` y `max_turns`

La llamada es la de siempre, con dos parámetros más:

```python
response = client.chat.completions.create(
    model=AI_CHEAP,                       # "openai:gpt-4.1-mini"
    messages=[{"role": "user", "content": prompt}],
    tools=[buscar_emails, enviar_email],  # funciones Python, no strings
    max_turns=5,                          # activa el loop y le pone techo
)
```

`aisuite` convierte las funciones en schemas, llama al modelo, ejecuta las
tools que pida, agrega los resultados a la conversación y vuelve a llamar.
Corta cuando el modelo responde sin pedir tools o al llegar a `max_turns`.
La respuesta final queda en `response.choices[0].message.content` y toda la
traza en `response.choices[0].intermediate_messages`.

### 1.4 El servidor de email

Las tools de este lab envuelven una API REST que corre en tu máquina: una
casilla simulada hecha con FastAPI + SQLAlchemy + SQLite, con el mismo patrón
que TaskFlow (`database.py`, `models.py`, `schemas.py`, endpoints en
`main.py`). Lo que antes llamaba el frontend con `fetch`, ahora lo llama una
función Python con `requests`, y a esa función la pide el modelo. Detalles en
`../email_server/README.md`.

## 2. Ejemplo resuelto

Pedido: *"Fijate si tengo mails sin leer de jefa@empresa.com. Si hay, marcalos
como leídos y respondele con un mail corto."*

Tools disponibles: `listar_no_leidos`, `buscar_emails`, `obtener_email`,
`enviar_email`, `buscar_no_leidos_de`, `marcar_como_leido`.

Traza que imprime `mostrar_traza` (*ejemplo ilustrativo; varía entre corridas*):

```
[modelo]  llama a buscar_no_leidos_de({'remitente': 'jefa@empresa.com'})
[tool]    buscar_no_leidos_de devolvió: lista de 1 elemento(s): [{"id": 3, "remitente": "jefa@empresa.com", "asunto": "Reporte trimestral", ...
[modelo]  llama a marcar_como_leido({'email_id': 3})
[tool]    marcar_como_leido devolvió: {"id": 3, ..., "leido": true}
[modelo]  llama a enviar_email({'destinatario': 'jefa@empresa.com', 'asunto': 'Re: Reporte trimestral', 'cuerpo': 'Hola Marina, ...'})
[tool]    enviar_email devolvió: {"id": 7, "remitente": "vos@empresa.com", ...}
[final]   Encontré un mail sin leer de la jefa sobre el reporte trimestral, lo marqué como leído y le respondí que se lo mando el miércoles.
Secuencia: buscar_no_leidos_de -> marcar_como_leido -> enviar_email
```

Qué mirar:

- El modelo eligió la tool compuesta `buscar_no_leidos_de` en vez de
  `listar_no_leidos` + filtrar a mano. El docstring ("usala cuando el pedido sea
  del tipo ¿tengo mails nuevos de X?") lo guió.
- El `email_id=3` que usa en el segundo paso **salió del resultado del
  primero**. Eso es encadenar: el modelo lee el JSON que devolvió la tool.
- Tres turnos de cinco. Si el pedido hubiera necesitado seis pasos, el loop se
  habría cortado a mitad de camino.
- La casilla cambió de verdad: `listar_todos()` después muestra el mail 3
  leído y un mail 7 nuevo. Por eso **reiniciamos la casilla** antes de cada
  experimento.

## 3. Práctica graduada

### Nivel base (los huecos del notebook, en orden)

1. **`marcar_como_leido(email_id)`** (sección 3.1). Es casi copiar
   `email_tools.marcar_como_no_leido`: cambiá la ruta a `/emails/{id}/read`.
   Escribí el docstring como si se lo explicaras a alguien que no ve el código.
2. **`buscar_no_leidos_de(remitente)`** (sección 3.2). Dos pasos: pedir los no
   leídos con `email_tools.listar_no_leidos()`; recorrerlos con un `for` y
   quedarte con los que tienen ese remitente, comparando con `.lower()` de los
   dos lados. Devolvé una lista (vacía si no hay).
3. **`armar_prompt(pedido)`** (sección 4). Un f-string multilínea con: rol,
   permiso para usar tools sin confirmar, `MI_EMAIL`, la fecha `hoy`, "respondé
   en español", y el pedido al final. Chequeá con `print` que las variables se
   hayan reemplazado.
4. **`mostrar_traza(response)`** (sección 5). Tres pasos. Para distinguir los
   dos tipos de elementos de `intermediate_messages`: los mensajes del modelo
   son objetos (`not isinstance(paso, dict)`) y tienen `.tool_calls`; los
   resultados son dicts con `"role": "tool"`. Los argumentos vienen como string
   JSON: `json.loads(call.function.arguments)`. Probala con
   `utils.respuesta_simulada()` antes de gastar una llamada real.
5. **`ejecutar_agente(pedido, tools, ...)`** (sección 6). La llamada de la
   sección 1.3 con `armar_prompt(pedido)` como contenido del mensaje.

Después de los huecos vienen los experimentos (secciones 6 a 8): correrlos,
leer las trazas y anotar qué secuencia eligió el modelo en cada caso.

### Extensión opcional (para los que terminan antes o para la casa)

1. **Docstring vago vs. preciso.** Definí `buscar(texto: str)` con el mismo
   código que `buscar_emails` pero docstring de una línea ("Busca."). Reemplazala
   en la lista de tools y corré el pedido de la sección 8 tres veces. ¿Cambia la
   secuencia? ¿Elige peor? Anotá los resultados.
2. **Tool compuesta nueva.** `responder_email(email_id: int, cuerpo: str) ->
   dict`: obtiene el mail, arma el asunto `Re: <asunto original>` y lo envía al
   remitente original. Dásela al agente y pedile "respondele a Sofía que el PATCH
   es parcial". Compará la traza con la del pedido equivalente sin esa tool.
3. **Instrucciones en `system`.** Cambiá `ejecutar_agente` para que las
   instrucciones vayan en `{"role": "system", ...}` y solo el pedido en `user`.
   ¿Cambia algo? (Es la forma más habitual en producción.)
4. **Medir turnos.** Contá los turnos en `mostrar_traza` (cada mensaje del
   modelo con `tool_calls` es uno). Corré el pedido de la sección 6 con
   `max_turns=2`. ¿Qué dice la respuesta final cuando el loop se corta antes de
   terminar? ¿Qué quedó hecho a medias en la casilla?

## 4. Troubleshooting de más a menos

De lo más grueso (nada funciona) a lo más fino (funciona pero raro).

| Síntoma | Causa probable | Arreglo |
|---|---|---|
| `verificar_servidor()` imprime `FALLA No hay nada escuchando en http://localhost:8000` o una tool lanza `ConnectionError: No pude conectarme al servidor...` | El servidor no está levantado, o se cerró la terminal donde corría. | En otra terminal, desde `M3-tool-use/`: `uvicorn email_server.main:app --reload --port 8000`. Dejala abierta. |
| `ModuleNotFoundError: No module named 'email_server'` al levantar uvicorn | Lo lanzaste desde `email_server/` o desde otra carpeta. | `cd` a `M3-tool-use/` y volvé a correr el comando. El `email_server.main` del comando es una ruta de import, no un archivo. |
| `verificar_servidor()` dice `respondió 404` o `no devolvió JSON` | `M3_EMAIL_SERVER_API_URL` del `.env` apunta a otro lado (otro puerto, una barra de más, un servidor distinto). | Revisá el `.env` de la raíz: `M3_EMAIL_SERVER_API_URL=http://localhost:8000`, sin barra final. Reiniciá el kernel después de cambiarlo. |
| `AssertionError: Falta OPENAI_API_KEY` o `AuthenticationError` al llamar al modelo | No hay `.env`, o la key está mal copiada, o el notebook no lo encuentra. | `cp .env.example .env` en la raíz del material y pegá la key. `find_dotenv(usecwd=True)` lo busca hacia arriba desde la carpeta del notebook; si Jupyter se abrió desde otra carpeta, no lo encuentra. |
| `TypeError: Parameter 'x' in function 'y' must have a type annotation` | Una tool tiene un parámetro sin type hint. `aisuite` no puede armar el schema. | Agregá el tipo: `def tool(email_id: int)`. |
| La traza muestra el modelo buscando y encontrando el mail pero la respuesta final dice "no puedo borrarlo" (o peor: dice que lo borró y sigue ahí) | La tool necesaria no está en la lista. Es el experimento de la sección 7, pero también pasa sin querer. | Revisá qué lista de tools le pasaste. Si el modelo *dice* que hizo algo que no podía hacer, es una alucinación de acción: el prompt debería pedirle que lo reconozca ("si no tenés una tool para hacerlo, decilo"). |
| Corrés el mismo pedido dos veces y la segunda vez el modelo dice "no hay mails sin leer de la jefa" | La primera corrida los marcó como leídos (o borró el mail). La casilla tiene estado. | `utils.reset_database()` antes de cada experimento. Compará trazas solo entre corridas que arrancaron igual. |
| La respuesta final está vacía o el modelo quedó "a mitad de camino" | Se agotó `max_turns`. | Subilo (6 u 8) o pedí menos cosas por pedido. Mirá la traza para ver cuántos turnos usó. |

## 5. Para cerrar

Tres preguntas de reflexión (para el chat de la clase o para tu cuaderno):

1. Si el servidor de email fuera el de tu empresa de verdad, ¿qué tools le
   darías al agente sin pensarlo y cuáles no? ¿Qué cambiaría en el prompt si
   quisieras que pida confirmación antes de borrar?
2. En la sección 7.1 el modelo no tenía `borrar_email`. ¿Qué hizo con la
   información que sí pudo conseguir? ¿Fue honesto sobre lo que no pudo hacer?
3. `buscar_no_leidos_de` es una combinación de dos tools que el modelo podría
   haber hecho solo. ¿Cuándo conviene darle combinaciones hechas y cuándo
   conviene darle piezas chicas?

Checklist de autoevaluación:

- [ ] Puedo explicar la diferencia entre "el modelo llama a una tool" y "el modelo ejecuta una función".
- [ ] Sé qué partes de una función usa `aisuite` para armar el schema y por qué el docstring importa.
- [ ] Escribí dos tools nuevas con type hints y docstrings completos y las vi funcionar en la traza.
- [ ] Puedo leer `intermediate_messages` y decir qué tool se llamó, con qué argumentos y qué devolvió.
- [ ] Vi con mis propios ojos que agregar una tool a la lista cambia lo que el agente puede hacer.
- [ ] Sé por qué hay que reiniciar la casilla entre experimentos.

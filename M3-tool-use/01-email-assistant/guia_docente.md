# Guía docente — Asistente de email con tools (aisuite)

## Ficha

| | |
|---|---|
| Duración | 2 h 15 min de las 3 h de la sesión 1 del módulo (los primeros 45 min son levantar y recorrer el servidor; ver `../README.md`). |
| Prerrequisitos | M2 completo (llamadas con `aisuite`, patrón de reflexión). Haber visto FastAPI en TaskFlow (endpoints, `/docs`). Python básico: funciones, dicts, listas, `for` con `if`, f-strings. |
| Keys | `OPENAI_API_KEY`. No usa Tavily. |
| Archivos | `lab.py` (fuente) → `notebook_alumno.ipynb` / `notebook_solucion.ipynb`; `email_tools.py` (tools dadas); `utils.py` (helpers y `respuesta_simulada`); `workbook.md`. Depende de `../email_server/` levantado. |
| Modelos | `MODEL_CHEAP` (`gpt-4.1-mini`) para todo el lab. `MODEL_STRONG` queda definido pero no se usa; sirve para que un alumno compare. |
| Costo estimado | Cada `ejecutar_agente` son entre 2 y 5 llamadas al modelo (un turno = una llamada). El notebook completo son 5 corridas: unas 15 a 25 llamadas por alumno, cortas. Con 20 alumnos y gpt-4.1-mini es un costo bajo; la extensión 1 (docstring vago, tres corridas) lo duplica. |
| Se evalúa | No. Es ungraded, como el original. La rúbrica de la sección final es orientativa. |

## Secuencia sugerida (sesión 1, 3 h)

| Minuto | Qué pasa | Quién |
|---|---|---|
| 0–10 | Quiz de apertura en el chat de la clase. Comentar las respuestas: la 3 (quién ejecuta la tool) es la que más confunde. | Todos |
| 10–45 | **Servidor de email.** Abrir `email_server/README.md`, mostrar la tabla "En TaskFlow / Acá". Levantarlo en vivo, abrir `/docs`, hacer los 5 pasos de prueba. Hacer que todos lo levanten y verifiquen con `/docs` antes de seguir (es la fuente número uno de problemas después). Mostrar `main.py` y señalar el orden de las rutas (`/emails/unread` antes de `/emails/{id}`). | Profesor en vivo, luego todos |
| 45–60 | Teoría breve (workbook §1.1–1.3): qué es una tool, el loop, el schema. Dibujar el diagrama de ida y vuelta en el pizarrón. | Profesor |
| 60–75 | Notebook secciones 1 y 2: verificar servidor, reset, llamar tools a mano, `mostrar_schema`. Detenerse en el schema de `filtrar_emails`: los parámetros con default no están en `required`. | Alumnos, el profesor recorre |
| 75–95 | Huecos 1 y 2 (`marcar_como_leido`, `buscar_no_leidos_de`). Son los fáciles; el objetivo es que todos los tengan funcionando contra el servidor. | Alumnos |
| 95–105 | Pausa. | |
| 105–125 | Huecos 3 y 4 (`armar_prompt`, `mostrar_traza`). `mostrar_traza` es el más largo: insistir en probarlo con `utils.respuesta_simulada()` antes de gastar llamadas. | Alumnos |
| 125–140 | Hueco 5 y primera corrida real (sección 6). Leer una traza en voz alta con el grupo: qué eligió, de dónde sacó el `email_id`. | Alumnos corren, profesor comenta |
| 140–165 | **Experimento central** (sección 7): sin `borrar_email` y con `borrar_email`. Pedir que levanten la mano quienes vieron al modelo *decir* que borró sin poder hacerlo. Discutir "alucinación de acción". Sección 8 (pedido ambiguo). | Alumnos, discusión |
| 165–180 | Cierre: las tres preguntas del workbook §5. Dejar la extensión opcional como tarea. Anticipar la sesión 2: "mañana vemos lo que aisuite hizo por nosotros a mano". | Profesor |

## Qué hacer en vivo vs. qué dejan corriendo los alumnos

**En vivo (profesor, pantalla compartida):**

- Levantar el servidor y recorrer `/docs`. Es la parte en la que vale la pena ir despacio: conecta con TaskFlow y desarma la idea de que "el modelo se conecta al servidor".
- `mostrar_schema(email_tools.filtrar_emails)` y leerlo línea por línea señalando de qué parte de la función salió cada cosa.
- Una traza real completa, leída en voz alta.
- La corrida 7.1 (sin `borrar_email`), porque el resultado varía y conviene comentar el que salga.

**Los alumnos corren solos:**

- Secciones 1 a 6 del notebook (huecos incluidos).
- Sección 7.2 y 8.
- Extensión opcional en casa.

**No conviene** que los alumnos ejecuten celdas con el modelo antes de tener `mostrar_traza` funcionando: sin traza no entienden qué pasó y gastan llamadas a ciegas.

## Dónde se traban (y qué decir)

Del inventario del material original y de lo que cuesta en este grupo (API, Python):

1. **El servidor.** El material original de DeepLearning.AI no incluía el código del servidor; corría en su plataforma. Acá lo levantan ellos. Problemas típicos: lanzar uvicorn desde la carpeta equivocada (`ModuleNotFoundError: email_server`), cerrar la terminal, puerto ocupado por otra cosa. Decir: "el comando `uvicorn email_server.main:app` se lee como `import email_server.main` y después `.app`; tiene que correrse desde la carpeta que contiene `email_server/`".
2. **"¿El modelo se conecta a mi localhost?"** No. El modelo devuelve texto estructurado que dice "llamá a X con Y"; `aisuite` (en la máquina del alumno) ejecuta la función. Volver al diagrama. Preguntar: "¿qué pasaría si apagás el servidor y el modelo pide `listar_no_leidos`?" (la tool lanza `ConnectionError`, el loop se corta; eso es tu código fallando, no el modelo).
3. **El docstring como prompt.** Algunos escriben las tools sin docstring porque "el código ya se entiende". Mostrar `mostrar_schema` de una función sin docstring: `"description": ""`. Preguntar: "¿cómo sabe el modelo qué hace esto?".
4. **`intermediate_messages` mezcla objetos y dicts.** Es raro y confunde: los mensajes del modelo son objetos del SDK (`paso.tool_calls`), los resultados son dicts (`paso["content"]`). Es la forma real que devuelve `aisuite` 0.2.0; la tabla de la sección 5 del notebook la describe. Si alguien pregunta por qué, la respuesta honesta es "porque la librería guarda tal cual lo que recibió del SDK y lo que armó ella".
5. **`call.function.arguments` es un string.** Hay que hacer `json.loads`. Si imprimen sin parsear ven `'{"email_id": 3}'` con comillas y creen que está bien.
6. **Resultados distintos entre corridas.** Dos causas que hay que separar: (a) el modelo no es determinista, puede elegir `buscar_emails` o `listar_no_leidos` para lo mismo; (b) la casilla tiene estado: si no la reiniciaron, la segunda corrida ve otra realidad. Insistir con `reset_database()` antes de comparar.
7. **El modelo "dice" que borró y no borró.** En 7.1 pasa con cierta frecuencia con el modelo barato. Es la mejor oportunidad del lab para hablar de alucinación de acción y de por qué el prompt tiene la línea "si no tenés una tool para hacer algo, decilo explícitamente". Pedirles que verifiquen con `buscar_emails("after")` después de cada corrida, no que confíen en la respuesta.
8. **Confunden `remitente` y `destinatario`.** En los mails que mandó el usuario, el remitente es `vos@empresa.com`. Si el pedido es "los mails que le mandé a la jefa", la tool correcta es `filtrar_emails(destinatario="jefa@empresa.com")`, no `buscar_emails("jefa")`. El prompt lo aclara, pero conviene decirlo.

## Respuestas del quiz de apertura

1. **b**. La reflexión son dos llamadas: la segunda recibe el borrador y una consigna de crítica (M2).
2. **a**. Validación explícita: ejecutar la consulta, chequear, y si falla devolver el error al modelo (M2 SQL).
3. **b**. El modelo devuelve un `tool_call` (nombre + argumentos en JSON); `aisuite` busca la función con ese nombre y la ejecuta en la máquina del alumno.
4. **b**. Firma (tipos, defaults) + docstring (descripción y `Args:`). Por eso el docstring es parte del prompt.
5. **b**. PATCH modifica parcialmente un recurso. GET solo lee; DELETE borra.

## Soluciones de la extensión opcional (esbozo)

1. **Docstring vago.** Con `"""Busca."""` el modelo suele seguir usándola (es la única que busca), pero a veces le pasa frases largas o la dirección completa en vez de una palabra, y en pedidos ambiguos alterna con `listar_no_leidos` + filtrado mental. El punto no es que falle siempre sino que la varianza sube. Pedir que anoten tres secuencias con cada versión.
2. **`responder_email`.**
   ```python
   def responder_email(email_id: int, cuerpo: str) -> dict:
       """Responde un email: lo envía al remitente original con asunto "Re: <asunto>". ..."""
       original = email_tools.obtener_email(email_id)
       if "error" in original:
           return original
       return email_tools.enviar_email(original["remitente"], f"Re: {original['asunto']}", cuerpo)
   ```
   Con esta tool, el pedido "respondele a Sofía" baja de 3 turnos (buscar → obtener → enviar) a 2 (buscar → responder).
3. **`system`.** `messages=[{"role": "system", "content": instrucciones}, {"role": "user", "content": pedido}]`. Con gpt-4.1 el comportamiento es casi idéntico; la ventaja es que en una conversación de varios mensajes las instrucciones no se repiten. Es la forma que se usa en el lab 02.
4. **`max_turns=2`.** El loop se corta después del segundo turno de tools: `aisuite` devuelve el último `response`, cuyo `message.content` suele ser `None` (el modelo estaba pidiendo otra tool). `mostrar_traza` imprime `[final] None`. En la casilla quedan hechos los pasos que alcanzó a dar (por ejemplo, marcado como leído pero sin responder). Buena entrada a la conversación sobre acciones a medias.

## Rúbrica (orientativa; el lab no se califica)

| Criterio | Logrado | En proceso |
|---|---|---|
| Tools nuevas | Las dos funcionan contra el servidor, con type hints y docstring con `Args:`/`Returns:` | Funcionan pero sin docstring o sin tipos (aisuite falla) |
| `armar_prompt` | Incluye rol, permiso, dirección, fecha e idioma; el pedido al final | Falta la fecha o la dirección; el modelo pregunta "¿cuál es tu mail?" |
| `mostrar_traza` | Distingue los dos tipos de pasos, parsea argumentos, devuelve la secuencia | Imprime los objetos crudos o no parsea `arguments` |
| Lectura del experimento | Explica con la traza por qué el agente no pudo borrar y qué cambió al agregar la tool | Repite "porque le falta la tool" sin mirar la traza |

## Diferencias con el lab original de DeepLearning.AI

| Original (M3_UGL_2) | Acá | Por qué |
|---|---|---|
| El servidor corría en la plataforma del curso; el código no está en el repo. | `email_server/` reconstruido (FastAPI + SQLAlchemy + SQLite) con tests. | Los alumnos lo levantan ellos; conecta con TaskFlow. |
| Datos semilla en inglés, con el usuario a veces `you@email.com` y a veces `you@mail.com`. | 6 mails en español, usuario único `vos@empresa.com`, fechas relativas a hoy. | La inconsistencia hacía fallar filtros por destinatario; las fechas fijas de 2025 volvían absurdo "esta semana". |
| Modelos `openai:gpt-4.1` y `openai:o4-mini`. | `MODEL_CHEAP` desde `.env`; nunca o4-mini. | Convenciones del material (modelos retirados). |
| Todas las tools dadas en `email_tools.py` (10, incluida `search_unread_from_sender`). | 8 dadas, traducidas, con docstrings cuidados; `marcar_como_leido` y `buscar_no_leidos_de` las escribe el alumno. | El original no tenía huecos; estas dos son el primer contacto con escribir una tool. |
| `build_prompt` dado, sin fecha. | `armar_prompt` es un hueco e incluye fecha y pedido de honestidad. | Sin fecha, "esta semana" no significa nada; la línea de honestidad reduce alucinaciones de acción. |
| `display_functions.pretty_print_chat_completion` (HTML con emojis) dado. | `mostrar_traza` es un hueco: imprime texto plano y devuelve la secuencia. | Recorrer `intermediate_messages` a mano es la mejor forma de entender el loop; devolver la secuencia permite compararla entre corridas. |
| `utils.py` con wrappers `test_*` que duplicaban las tools, y `call_llm_email_agent` para un segundo servidor LLM. | `utils.py` mínimo: verificar servidor, reset, mostrar, schema, `respuesta_simulada`. | Los wrappers `test_*` confundían (dos formas de llamar lo mismo); el servidor LLM no se usa. |
| Las tools hacían `.json()` directo: un 404 o un servidor caído daban excepciones crípticas. | `_pedir` traduce conexión caída a un `ConnectionError` con instrucciones, y 4xx a `{"error": ..., "status": ...}` que el modelo puede leer. | Troubleshooting de más a menos; el modelo aprende del error en vez de cortar el loop. |
| Experimento "borrar sin la tool" presente pero sin verificación posterior. | Se verifica con `buscar_emails("after")` después de cada corrida y se compara la secuencia. | Separar lo que el modelo *dice* de lo que *pasó*. |
| Sin quiz, workbook ni guía. | Agregados según convenciones. | |

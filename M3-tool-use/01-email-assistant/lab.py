# %% [markdown]
# # Asistente de email con tools (aisuite)
# **Módulo 3 · Lab 01.** Un agente que administra una casilla de correo simulada:
# vos le pedís en lenguaje natural ("fijate si hay mails de la jefa y respondele") y
# él decide qué funciones Python llamar, en qué orden y con qué argumentos.
#
# ## Objetivos
# Al terminar vas a poder:
# - Explicar qué es una tool y por qué el docstring de la función es lo que "lee" el modelo.
# - Convertir endpoints de una API REST en tools para un LLM.
# - Lanzar el loop de tool use con `aisuite` (`tools=[...]`, `max_turns=...`).
# - Leer la traza de una corrida: qué tool se llamó, con qué argumentos y qué devolvió.
# - Demostrar que **las tools disponibles definen lo que el agente puede hacer**.

# %% [markdown]
# ## Antes de empezar: quiz de apertura
# Respondé mentalmente (o en el chat de la clase) antes de leer la teoría.
#
# 1. En el patrón de reflexión del módulo anterior, ¿qué recibía la segunda llamada al modelo?
#    a) El mismo prompt que la primera, para probar suerte otra vez.
#    b) El borrador generado más una consigna de criticarlo.
#    c) Solo la crítica, sin el borrador.
# 2. En M2, cuando el modelo generaba una consulta SQL, ¿qué hacíamos antes de confiar en ella?
#    a) La ejecutábamos y validábamos el resultado (y si fallaba, el error volvía al modelo).
#    b) La copiábamos tal cual al informe.
#    c) Le pedíamos al modelo que prometiera que estaba bien.
# 3. Cuando el modelo "llama a una tool", ¿quién ejecuta la función?
#    a) El modelo, en los servidores de OpenAI.
#    b) Tu código (acá, `aisuite`), en tu máquina; el modelo solo pide la llamada.
#    c) El servidor de email, que la recibe directo del modelo.
# 4. ¿De dónde saca `aisuite` la descripción de una tool para mostrársela al modelo?
#    a) Solo del nombre de la función.
#    b) De la firma (tipos y defaults) más el docstring.
#    c) La escribe el modelo la primera vez que la usa.
# 5. En una API REST, ¿qué método HTTP corresponde a "marcar un mail como leído"?
#    a) GET   b) PATCH   c) DELETE

# %% [markdown] solo-profesor
# **Respuestas del quiz:** 1-b (reflexión = borrador + consigna de crítica, dos llamadas),
# 2-a (validación explícita: ejecutar, chequear, devolver el error al modelo),
# 3-b (el modelo devuelve un `tool_call` con nombre y argumentos JSON; aisuite busca la función y la ejecuta),
# 4-b (firma + docstring; por eso los docstrings son parte del "prompt"),
# 5-b (PATCH modifica parcialmente un recurso; GET solo lee, DELETE borra).

# %%
# Setup: claves y modelos salen del archivo .env de la raíz del material
import json
import os
from datetime import date

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4.1-mini")    # generar, tools, rutear
MODEL_STRONG = os.getenv("MODEL_STRONG", "gpt-4.1")       # reflexionar, criticar, ver imágenes
assert os.getenv("OPENAI_API_KEY"), "Falta OPENAI_API_KEY: copiá .env.example a .env en la raíz del material"

import aisuite as ai

client = ai.Client()
AI_CHEAP = f"openai:{MODEL_CHEAP}"     # aisuite quiere "proveedor:modelo"
AI_STRONG = f"openai:{MODEL_STRONG}"

import utils
import email_tools

MI_EMAIL = utils.MI_EMAIL              # "vos@empresa.com": tu dirección en la casilla simulada
print("Modelos:", AI_CHEAP, "|", AI_STRONG)
print("Servidor de email:", email_tools.BASE_URL)

# %% [markdown]
# ## 1. El servidor de email (lo que ya conocés)
#
# El agente va a trabajar sobre una casilla simulada que corre en tu máquina: una
# API REST hecha con FastAPI + SQLAlchemy + SQLite, **el mismo patrón que TaskFlow**.
# Tiene 10 endpoints (`GET /emails`, `POST /send`, `PATCH /emails/{id}/read`, ...);
# la lista completa está en `email_server/README.md`.
#
# Tiene que estar levantado en otra terminal, desde la carpeta `M3-tool-use/`:
#
# ```bash
# uvicorn email_server.main:app --reload --port 8000
# ```
#
# La celda siguiente lo verifica y reinicia la casilla a sus 6 mails iniciales.
# **Reiniciá la casilla cada vez que empieces un experimento**: si no, cada corrida
# ve una casilla distinta (mails ya leídos, ya borrados) y los resultados no se
# pueden comparar.

# %%
assert utils.verificar_servidor(), "Levantá el servidor antes de seguir (ver instrucciones arriba)"
print(utils.reset_database())
utils.mostrar_emails(email_tools.listar_todos())

# %% [markdown]
# ## 2. Tools: funciones Python que el modelo puede pedir que ejecutes
#
# **Para qué.** Un LLM solo produce texto. Para que *haga* algo (leer la casilla,
# mandar un mail) necesita que alguien ejecute código por él. Una **tool** es una
# función Python que vos ponés a disposición del modelo: él decide *cuándo* llamarla
# y *con qué argumentos*; tu código la ejecuta y le devuelve el resultado.
#
# **Por qué así.** El modelo nunca toca la API directamente. Lo que viaja es:
#
# ```
# vos ──pedido──▶ modelo ──"llamá a buscar_emails(texto='reporte')"──▶ aisuite ejecuta la función
#                 modelo ◀──────── resultado (JSON) ────────────────── aisuite
#                 modelo ──"llamá a marcar_como_leido(email_id=3)"──▶ ...
#                 modelo ──respuesta final en texto──▶ vos
# ```
#
# Ese ida y vuelta es el **loop de tool use**. Con `aisuite`, lo activa el parámetro
# `max_turns`: cada "turno" es una llamada al modelo seguida de la ejecución de las
# tools que pidió. Se corta cuando el modelo responde sin pedir tools, o al llegar a
# `max_turns`.
#
# **Ejemplo práctico.** En `email_tools.py` hay una función por endpoint. Mirá una:
#
# ```python
# def buscar_emails(texto: str) -> list[dict]:
#     """Busca emails que contengan el texto en el asunto, el cuerpo o el remitente.
#
#     No distingue mayúsculas. Usala para encontrar un mail por tema ("after",
#     "reporte") o por remitente ("jefa@empresa.com").
#
#     Args:
#         texto: palabra o frase a buscar. Ej: "reporte".
#     ...
#     """
#     return _pedir("GET", "/emails/search", params={"q": texto})
# ```
#
# Es una función común: hace un `GET` y devuelve el JSON. Lo que la convierte en tool
# es cómo se la pasás al modelo. Primero probala a mano, como cualquier función.

# %%
# Las tools son funciones normales: se pueden llamar sin ningún modelo en el medio
print("Búsqueda 'reporte':")
utils.mostrar_emails(email_tools.buscar_emails("reporte"))

print("\nNo leídos:")
utils.mostrar_emails(email_tools.listar_no_leidos())

nuevo = email_tools.enviar_email("sofia@empresa.com", "Re: Duda sobre el endpoint", "Mandá solo el campo estado, el PATCH es parcial.")
print("\nEnviado:", nuevo["id"], nuevo["asunto"], "->", nuevo["destinatario"])

# %% [markdown]
# ### 2.1 El docstring ES la documentación que lee el modelo
#
# Cuando le pasás una función a `aisuite`, él arma un **schema JSON** a partir de la
# firma (nombres de parámetros, tipos, defaults) y del docstring (descripción
# general y descripción de cada `Args:`). Ese schema es lo único que el modelo ve de
# tu función: no ve el código, no ve los comentarios, no ve el nombre del archivo.
#
# Conclusión práctica: el docstring es parte del prompt. Si dice "busca emails", el
# modelo sabrá que existe; si además dice *cuándo* conviene usarla y da un ejemplo
# de argumento, el modelo la va a usar mejor. Mirá el schema que genera para
# `buscar_emails` y para `filtrar_emails` (fijate cómo aparecen los parámetros
# opcionales).

# %%
utils.mostrar_schema(email_tools.buscar_emails)

# %%
utils.mostrar_schema(email_tools.filtrar_emails)

# %% [markdown]
# ## 3. Dos tools que faltan (las escribís vos)
#
# En `email_tools.py` faltan dos tools a propósito. Las escribís acá, en el notebook,
# siguiendo el mismo estilo: type hints en todos los parámetros (si falta uno,
# `aisuite` lanza `TypeError`), docstring en español con `Args:` y `Returns:`.
#
# ### 3.1 `marcar_como_leido`
# Es casi copiar `marcar_como_no_leido`: cambia la ruta (`/read` en vez de
# `/unread`) y el texto del docstring. El helper `email_tools._pedir(metodo, ruta)`
# hace la request y devuelve el JSON.

# %%
def marcar_como_leido(email_id: int) -> dict:
    """Marca un email como leído.

    Usala después de procesar un mail (leerlo, responderlo) para que no vuelva a
    aparecer entre los no leídos.

    Args:
        email_id: id numérico del email (el campo "id" que devuelven las otras tools).

    Returns:
        El email actualizado (leido = true). Si el id no existe, dict con la clave "error".
    """
    ### BEGIN SOLUTION
    ### STUDENT: # Pista: mirá email_tools.marcar_como_no_leido y cambiá la ruta
    ### STUDENT: raise NotImplementedError("Completá esta función")
    return email_tools._pedir("PATCH", f"/emails/{email_id}/read")
    ### END SOLUTION

# %%
# Prueba rápida: el mail 3 (de la jefa) pasa a leído y deja de aparecer en no leídos
print(marcar_como_leido(3)["leido"])
utils.mostrar_emails(email_tools.listar_no_leidos())
print("\nSi un id no existe, la tool no explota: devuelve un error que el modelo puede leer")
print(marcar_como_leido(999))
print("\nSchema que va a ver el modelo:")
utils.mostrar_schema(marcar_como_leido)

# %% [markdown]
# ### 3.2 `buscar_no_leidos_de`
# Esta no corresponde a un endpoint: **combina** dos cosas que ya existen. Pide los
# no leídos con `email_tools.listar_no_leidos()` y se queda con los que tienen ese
# remitente (comparando en minúsculas, para que `Jefa@Empresa.com` también
# funcione).
#
# ¿Por qué una tool "compuesta" si el modelo podría hacerlo en dos pasos? Porque
# cada paso es una llamada al modelo (tiempo y plata) y una oportunidad de error.
# Si una combinación es frecuente, conviene dársela hecha.

# %%
def buscar_no_leidos_de(remitente: str) -> list[dict]:
    """Devuelve los emails NO leídos que mandó un remitente determinado.

    Usala cuando el pedido sea del tipo "¿tengo mails nuevos de X?". Compara la
    dirección completa sin distinguir mayúsculas.

    Args:
        remitente: dirección de email del remitente. Ej: "jefa@empresa.com".

    Returns:
        Lista de dicts con los emails no leídos de ese remitente; vacía si no hay.
    """
    # Paso 1: traer todos los no leídos
    ### BEGIN SOLUTION
    no_leidos = email_tools.listar_no_leidos()
    ### END SOLUTION
    # Paso 2: quedarte solo con los de ese remitente (comparación en minúsculas)
    ### BEGIN SOLUTION
    resultado = []
    for email in no_leidos:
        if email["remitente"].lower() == remitente.lower():
            resultado.append(email)
    return resultado
    ### END SOLUTION

# %%
# Prueba rápida: reiniciamos la casilla para que el mail de la jefa vuelva a estar sin leer
utils.reset_database()
utils.mostrar_emails(buscar_no_leidos_de("JEFA@empresa.com"))
print()
utils.mostrar_emails(buscar_no_leidos_de("nadie@empresa.com"))

# %% [markdown]
# ## 4. El prompt del agente
#
# El pedido del usuario ("borrá el mail del after") va envuelto en instrucciones que
# le dicen al modelo quién es, qué permisos tiene y qué contexto necesita:
#
# - que es un asistente de email y que **use las tools** (sin eso, a veces responde
#   "para hacer eso necesitaría acceso a tu casilla");
# - que **no pida confirmación** (en este lab no hay humano en el loop; en M4 vamos
#   a discutir cuándo sí conviene pedirla);
# - **tu dirección** (`vos@empresa.com`), para que sepa qué es "mío";
# - **la fecha de hoy**, para que "esta semana" o "ayer" signifiquen algo;
# - que **responda en español** y resuma qué hizo.
#
# Escribí `armar_prompt` para que devuelva ese texto con el pedido al final.

# %%
def armar_prompt(pedido: str) -> str:
    """Envuelve el pedido del usuario con las instrucciones del asistente de email.

    El texto resultante va como único mensaje de rol "user". Tiene que incluir:
    rol del asistente, permiso para usar tools sin pedir confirmación, tu dirección
    (MI_EMAIL), la fecha de hoy y la indicación de responder en español. El pedido
    va al final.

    Args:
        pedido: lo que quiere el usuario, en lenguaje natural.

    Returns:
        El prompt completo, listo para mandar al modelo.
    """
    hoy = date.today().isoformat()
    ### BEGIN SOLUTION
    ### STUDENT: instrucciones = f"""..."""  # Pista: f-string multilínea con MI_EMAIL y hoy adentro
    ### STUDENT: raise NotImplementedError("Completá esta función")
    instrucciones = f"""Sos un asistente que administra mi casilla de email.
- Usá las tools disponibles para listar, buscar, leer, enviar y modificar mails.
- Nunca pidas confirmación: ejecutá directamente lo que te pido.
- Mi dirección es {MI_EMAIL}. Los mails donde soy el destinatario son los que recibí; los que tienen mi dirección como remitente son los que mandé.
- Hoy es {hoy}. Usá esa fecha para interpretar expresiones como "esta semana" o "ayer".
- Si no tenés una tool para hacer algo, decilo explícitamente; no digas que lo hiciste.
- Respondé en español, resumiendo en una o dos frases qué hiciste.

Pedido: {pedido.strip()}
"""
    return instrucciones
    ### END SOLUTION

# %%
print(armar_prompt("Borrá el mail del after del viernes"))

# %% [markdown]
# ## 5. Leer la traza: qué hizo el agente paso a paso
#
# Cuando usás `max_turns`, `aisuite` guarda todo el ida y vuelta en
# `response.choices[0].intermediate_messages`. Es una lista con dos tipos de
# elementos, en orden cronológico:
#
# | Tipo                       | Cómo lo reconocés                              | Qué tiene adentro                                         |
# |----------------------------|------------------------------------------------|-----------------------------------------------------------|
# | Mensaje del modelo         | es un objeto, con atributo `.tool_calls`       | lista de `call`; cada uno con `call.function.name` y `call.function.arguments` (un string JSON) |
# | Resultado de una tool      | es un `dict` con `"role": "tool"`              | `"name"` (la tool), `"content"` (el resultado, como string JSON), `"tool_call_id"` |
#
# El último elemento es el mensaje final del modelo (sin `tool_calls`); también está
# en `response.choices[0].message.content`.
#
# Escribí `mostrar_traza` para imprimir, en orden, cada llamada con sus argumentos y
# cada resultado resumido, y al final la respuesta y la secuencia de tools. Vas a
# usarla en todos los experimentos que siguen, así que vale la pena que quede
# legible. Para probarla sin gastar llamadas, `utils.respuesta_simulada()` devuelve
# un `response` con la misma forma que el real.

# %%
def mostrar_traza(response) -> list[str]:
    """Imprime el paso a paso de una corrida con tools y devuelve la secuencia de nombres de tools.

    Recorre response.choices[0].intermediate_messages en orden. Para cada mensaje
    del modelo con tool_calls imprime "[modelo] llama a <tool>(<args>)"; para cada
    resultado de tool imprime "[tool] <tool> devolvió: <resumen>". Al final imprime
    la respuesta y la secuencia de tools unida con " -> ".

    Args:
        response: lo que devuelve client.chat.completions.create(..., tools=..., max_turns=...).

    Returns:
        Lista con los nombres de las tools llamadas, en orden (vacía si no llamó ninguna).
    """
    pasos = response.choices[0].intermediate_messages
    secuencia = []
    for paso in pasos:
        # Paso 1: si es un mensaje del modelo (no es dict) con tool_calls, imprimir tool y argumentos
        ### BEGIN SOLUTION
        if not isinstance(paso, dict) and paso.tool_calls:
            for call in paso.tool_calls:
                args = json.loads(call.function.arguments)
                secuencia.append(call.function.name)
                print(f"[modelo]  llama a {call.function.name}({args})")
        ### END SOLUTION
        # Paso 2: si es un dict con role "tool", imprimir el resultado resumido (utils.resumir)
        ### BEGIN SOLUTION
        if isinstance(paso, dict) and paso.get("role") == "tool":
            resultado = json.loads(paso["content"])
            print(f"[tool]    {paso['name']} devolvió: {utils.resumir(resultado)}")
        ### END SOLUTION
    # Paso 3: respuesta final y secuencia de tools (o avisar que no llamó ninguna)
    ### BEGIN SOLUTION
    print(f"[final]   {response.choices[0].message.content}")
    if secuencia:
        print("Secuencia:", " -> ".join(secuencia))
    else:
        print("Secuencia: (no llamó ninguna tool)")
    ### END SOLUTION
    return secuencia

# %%
# Prueba rápida sin API: un response simulado con dos tool calls
secuencia = mostrar_traza(utils.respuesta_simulada())
assert secuencia == ["buscar_no_leidos_de", "marcar_como_leido"], secuencia
print("\nmostrar_traza OK")

# %% [markdown]
# ## 6. El agente en acción
#
# Ahora sí: el modelo toma el control. La llamada es la misma que en M2 más dos
# parámetros:
#
# - `tools=[...]`: la lista de **funciones** (no strings, no schemas; `aisuite` arma
#   el schema por vos).
# - `max_turns=5`: activa el loop y le pone un techo.
#
# Completá `ejecutar_agente`. Después corré el pedido de ejemplo y leé la traza:
# ¿qué tool eligió primero? ¿con qué argumentos? ¿cuántos turnos usó?

# %%
TOOLS_BASE = [
    email_tools.listar_no_leidos,
    email_tools.buscar_emails,
    email_tools.obtener_email,
    email_tools.enviar_email,
    buscar_no_leidos_de,       # las dos que escribiste vos
    marcar_como_leido,
]


def ejecutar_agente(pedido: str, tools: list, model: str = AI_CHEAP, max_turns: int = 5):
    """Arma el prompt, lanza el loop de tool use y devuelve el response completo.

    Args:
        pedido: lo que quiere el usuario, en lenguaje natural.
        tools: lista de funciones Python que el modelo puede llamar.
        model: modelo en formato aisuite ("openai:gpt-4.1-mini").
        max_turns: cantidad máxima de turnos (llamada al modelo + ejecución de tools).

    Returns:
        El response de aisuite; la traza está en response.choices[0].intermediate_messages.
    """
    prompt = armar_prompt(pedido)
    ### BEGIN SOLUTION
    ### STUDENT: response = None  # Pista: client.chat.completions.create(model=..., messages=[...], tools=..., max_turns=...)
    ### STUDENT: raise NotImplementedError("Completá esta función")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        max_turns=max_turns,
    )
    ### END SOLUTION
    return response

# %%
utils.reset_database()
response = ejecutar_agente(
    "Fijate si tengo mails sin leer de jefa@empresa.com. Si hay, marcalos como leídos y "
    "respondele con un mail corto diciendo que le mando lo que pide el miércoles.",
    tools=TOOLS_BASE,
)
secuencia = mostrar_traza(response)

# %%
# ¿Quedó reflejado en la casilla? El mail de la jefa ya no está en no leídos y hay un mail nuevo enviado por vos
utils.mostrar_emails(email_tools.listar_todos())

# %% [markdown]
# ## 7. Experimento central: la tool que falta
#
# **Las tools disponibles determinan lo que el agente puede hacer.** Vamos a
# comprobarlo con el mismo pedido dos veces.
#
# ### 7.1 Sin `borrar_email`
# `TOOLS_BASE` no incluye `email_tools.borrar_email`. Pedile que borre un mail y mirá
# la traza: probablemente lo *encuentre* (tiene `buscar_emails`) pero no pueda
# borrarlo. Fijate **qué dice** en la respuesta final: ¿reconoce que no puede, o
# inventa que lo hizo? Esto último se llama alucinación de acción y es uno de los
# riesgos a vigilar en agentes.

# %%
utils.reset_database()
PEDIDO_BORRAR = "Borrá el mail del after del viernes."

response = ejecutar_agente(PEDIDO_BORRAR, tools=TOOLS_BASE)
secuencia_sin = mostrar_traza(response)
print("\n¿Sigue en la casilla?", len(email_tools.buscar_emails("after")) == 1)

# %% [markdown]
# ### 7.2 Con `borrar_email`
# Mismo pedido, mismo prompt, mismo modelo. Lo único que cambia es la lista de tools.

# %%
TOOLS_CON_BORRADO = TOOLS_BASE + [email_tools.borrar_email]

utils.reset_database()
response = ejecutar_agente(PEDIDO_BORRAR, tools=TOOLS_CON_BORRADO)
secuencia_con = mostrar_traza(response)
print("\n¿Sigue en la casilla?", len(email_tools.buscar_emails("after")) == 1)

print("\nSin borrar_email:", " -> ".join(secuencia_sin) or "(nada)")
print("Con borrar_email:", " -> ".join(secuencia_con) or "(nada)")

# %% [markdown]
# ## 8. Un pedido más ambiguo
#
# "Borrá el mail de Tomás" no tiene la dirección exacta ni el asunto. Mirá cómo lo
# resuelve el modelo: ¿busca por "tomas"? ¿lista todo y filtra? ¿pide el mail
# completo antes de borrarlo? No hay una única secuencia correcta; lo que importa
# es que llegue al resultado y que la traza sea entendible. Corré la celda dos o
# tres veces (reiniciando la casilla) y compará las secuencias.

# %%
utils.reset_database()
response = ejecutar_agente("Borrá el mail de Tomás sobre el PR.", tools=TOOLS_CON_BORRADO)
mostrar_traza(response)
print("\nMails de Tomás que quedan:", len(email_tools.buscar_emails("tomas@")))

# %% [markdown]
# ## 9. Si te sobra tiempo
#
# Consignas abiertas, sin solución en el notebook (hay pistas en el workbook):
#
# 1. **Docstring vago vs. preciso.** Copiá `buscar_emails` a una función
#    `buscar(texto: str)` con docstring de una sola línea ("Busca.") y reemplazala en
#    `TOOLS_CON_BORRADO`. Corré el pedido de la sección 8 varias veces. ¿Cambia la
#    secuencia? ¿El modelo elige peor?
# 2. **Tool compuesta nueva.** Escribí `responder_email(email_id: int, cuerpo: str)`
#    que obtenga el mail, arme el asunto `Re: <asunto original>` y lo envíe al
#    remitente. Dásela al agente y pedile "respondele a Sofía que el PATCH es parcial".
# 3. **Instrucciones en `system`.** Cambiá `ejecutar_agente` para que las
#    instrucciones vayan en un mensaje `{"role": "system", ...}` y el pedido en el
#    `user`. ¿Cambia algo en el comportamiento?
# 4. **Medir turnos.** Agregá un contador en `mostrar_traza` que imprima cuántos
#    turnos usó cada corrida. Repetí el pedido de la sección 6 con `max_turns=2`:
#    ¿qué pasa cuando el loop se corta antes de terminar?

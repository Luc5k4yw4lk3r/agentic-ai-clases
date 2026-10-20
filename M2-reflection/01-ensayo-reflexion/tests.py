"""Chequeos del lab 01 — Ensayo con reflexión.

Dos formas de usarlos:

1. Desde el notebook, al final:

       from tests import run_all
       run_all(generar_borrador, reflexionar_sobre_borrador, revisar_borrador,
               reflexionar_en_bucle=reflexionar_en_bucle, client=client)

   Con `client=None` solo corren los chequeos estructurales (sin API).

2. Desde la terminal, en esta carpeta: `pytest -q`
   Carga las funciones desde `notebook_solucion.ipynb` si existe (entorno del
   profesor) o, si no, desde `notebook_alumno.ipynb` (entorno del alumno: guardá
   el notebook antes de correrlo). Nunca llama a la API.

Los chequeos estructurales usan un `FakeClient`: un objeto con la misma forma que
el cliente de aisuite (`client.chat.completions.create(...)` devuelve algo con
`.choices[0].message.content`) que no llama a ninguna API y anota qué prompt
recibió. Así podemos verificar que `revisar_borrador` manda el borrador Y la
crítica, sin gastar una llamada ni depender del texto que devuelva el modelo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

AQUI = Path(__file__).resolve().parent
FUNCIONES_DEL_LAB = (
    "preguntar",
    "generar_borrador",
    "reflexionar_sobre_borrador",
    "revisar_borrador",
    "reflexionar_en_bucle",
)


# ---------------------------------------------------------------------------
# Cliente falso
# ---------------------------------------------------------------------------
def respuesta_simulada(texto: str):
    """Arma un objeto con la forma de la respuesta de aisuite/OpenAI.

    Lo único que las funciones del lab leen es `response.choices[0].message.content`.
    """
    message = SimpleNamespace(content=texto, role="assistant")
    choice = SimpleNamespace(message=message, finish_reason="stop", index=0)
    return SimpleNamespace(choices=[choice], usage=None)


class FakeClient:
    """Imita a `aisuite.Client()` sin llamar a ninguna API.

    - `respuestas`: lista opcional de textos que va a devolver en orden. Si se
      agota (o no se pasa), devuelve un texto genérico numerado.
    - `llamadas`: lista de dicts con lo que recibió cada llamada
      (`model`, `messages`, `prompt` = contenido del último mensaje).
    """

    def __init__(self, respuestas: list[str] | None = None):
        self.llamadas: list[dict] = []
        self._respuestas = list(respuestas) if respuestas else []
        # client.chat.completions.create(...) tiene que existir con esa ruta exacta
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model: str, messages: list, **kwargs):
        prompt = messages[-1]["content"] if messages else ""
        self.llamadas.append({"model": model, "messages": messages, "prompt": prompt, "kwargs": kwargs})
        if self._respuestas:
            texto = self._respuestas.pop(0)
        else:
            texto = f"RESPUESTA SIMULADA {len(self.llamadas)}. " + ("palabra " * 120).strip()
        return respuesta_simulada(texto)

    @property
    def ultimo_prompt(self) -> str:
        return self.llamadas[-1]["prompt"] if self.llamadas else ""


class _ClienteFalsoActivo:
    """Reemplaza temporalmente la variable global `client` que usan las funciones.

    Las funciones del notebook no reciben el cliente por parámetro: usan `client`
    del espacio global del notebook. Para probarlas sin API, pisamos esa variable
    en `fn.__globals__` mientras dura el chequeo y después la restauramos.
    """

    def __init__(self, funciones, fake: FakeClient):
        self.globales = []
        vistos = set()
        for fn in funciones:
            if fn is None:
                continue
            g = fn.__globals__
            if id(g) not in vistos:
                vistos.add(id(g))
                self.globales.append(g)
        self.fake = fake
        self.anteriores = []

    def __enter__(self):
        for g in self.globales:
            self.anteriores.append(g.get("client", None))
            g["client"] = self.fake
        return self.fake

    def __exit__(self, *exc):
        for g, anterior in zip(self.globales, self.anteriores):
            g["client"] = anterior
        return False


# ---------------------------------------------------------------------------
# Chequeos estructurales (sin API)
# ---------------------------------------------------------------------------
MODELO_DE_PRUEBA = "openai:modelo-de-prueba"


def check_generar_borrador(generar_borrador, otras=()):
    fake = FakeClient(respuestas=["ENSAYO-SIMULADO sobre el tema pedido."])
    with _ClienteFalsoActivo([generar_borrador, *otras], fake):
        salida = generar_borrador("¿Los videojuegos educan?", model=MODELO_DE_PRUEBA)
    assert isinstance(salida, str), f"Tiene que devolver str, devolvió {type(salida).__name__}"
    assert len(fake.llamadas) == 1, f"Esperaba exactamente 1 llamada al modelo, hubo {len(fake.llamadas)}"
    assert "videojuegos" in fake.ultimo_prompt, "La consigna no aparece en el prompt que se mandó al modelo"
    assert fake.llamadas[0]["model"] == MODELO_DE_PRUEBA, "No está usando el parámetro `model`: lo tiene hardcodeado"
    assert salida == "ENSAYO-SIMULADO sobre el tema pedido.", (
        "Tiene que devolver exactamente `response.choices[0].message.content`, no otra cosa"
    )


def check_reflexionar_sobre_borrador(reflexionar_sobre_borrador, otras=()):
    fake = FakeClient(respuestas=["CRITICA-SIMULADA: faltan ejemplos."])
    borrador = "BORRADOR-MARCA-123. Este es un ensayo de prueba con varias oraciones."
    with _ClienteFalsoActivo([reflexionar_sobre_borrador, *otras], fake):
        salida = reflexionar_sobre_borrador(borrador, model=MODELO_DE_PRUEBA)
    assert isinstance(salida, str), f"Tiene que devolver str, devolvió {type(salida).__name__}"
    assert len(fake.llamadas) == 1, f"Esperaba exactamente 1 llamada al modelo, hubo {len(fake.llamadas)}"
    assert "BORRADOR-MARCA-123" in fake.ultimo_prompt, "El borrador no aparece en el prompt: el modelo no tiene qué criticar"
    assert fake.llamadas[0]["model"] == MODELO_DE_PRUEBA, "No está usando el parámetro `model`"
    assert salida == "CRITICA-SIMULADA: faltan ejemplos.", "Tiene que devolver el texto de la respuesta del modelo"


def check_revisar_borrador(revisar_borrador, otras=()):
    fake = FakeClient(respuestas=["REVISION-SIMULADA del ensayo, ya corregida."])
    borrador = "BORRADOR-MARCA-123. Texto original del ensayo."
    critica = "CRITICA-MARCA-456. Le faltan ejemplos y la conclusión es débil."
    with _ClienteFalsoActivo([revisar_borrador, *otras], fake):
        salida = revisar_borrador(borrador, critica, model=MODELO_DE_PRUEBA)
    assert isinstance(salida, str), f"Tiene que devolver str, devolvió {type(salida).__name__}"
    assert len(fake.llamadas) == 1, f"Esperaba exactamente 1 llamada al modelo, hubo {len(fake.llamadas)}"
    prompt = fake.ultimo_prompt
    assert "BORRADOR-MARCA-123" in prompt, "El borrador no aparece en el prompt: el modelo no tiene qué revisar"
    assert "CRITICA-MARCA-456" in prompt, "La crítica no aparece en el prompt: la revisión no está usando la reflexión"
    assert fake.llamadas[0]["model"] == MODELO_DE_PRUEBA, "No está usando el parámetro `model`"
    assert salida != borrador, "La revisión es idéntica al borrador: tiene que devolver la salida del modelo"
    assert salida == "REVISION-SIMULADA del ensayo, ya corregida.", "Tiene que devolver el texto de la respuesta del modelo"


def check_reflexionar_en_bucle(reflexionar_en_bucle, otras=()):
    # Respuestas en el orden en que el bucle debería pedirlas: V1, c1, V2, c2, V3
    guion = ["VERSION-UNO", "CRITICA-UNO", "VERSION-DOS", "CRITICA-DOS", "VERSION-TRES"]
    fake = FakeClient(respuestas=list(guion))
    with _ClienteFalsoActivo([reflexionar_en_bucle, *otras], fake):
        resultado = reflexionar_en_bucle("¿Tema de prueba?", rondas=2, model=MODELO_DE_PRUEBA)
    assert isinstance(resultado, dict), f"Tiene que devolver un dict, devolvió {type(resultado).__name__}"
    assert set(resultado.keys()) >= {"borradores", "criticas"}, f"Faltan claves: {sorted(resultado.keys())}"
    assert len(fake.llamadas) == 5, f"Con rondas=2 son 5 llamadas (1 + 2×2), hubo {len(fake.llamadas)}"
    assert resultado["borradores"] == ["VERSION-UNO", "VERSION-DOS", "VERSION-TRES"], (
        f"borradores tiene que ser [V1, V2, V3]; devolvió {resultado['borradores']}"
    )
    assert resultado["criticas"] == ["CRITICA-UNO", "CRITICA-DOS"], (
        f"criticas tiene que ser [c1, c2]; devolvió {resultado['criticas']}"
    )
    # Encadenamiento: cada vuelta trabaja sobre el ÚLTIMO borrador, no sobre el primero
    prompts = [ll["prompt"] for ll in fake.llamadas]
    assert "VERSION-UNO" in prompts[1], "La primera crítica no recibió V1"
    assert "VERSION-UNO" in prompts[2] and "CRITICA-UNO" in prompts[2], "La primera revisión no recibió V1 y c1"
    assert "VERSION-DOS" in prompts[3], "La segunda crítica tiene que criticar V2 (el último borrador), no V1"
    assert "VERSION-DOS" in prompts[4] and "CRITICA-DOS" in prompts[4], "La segunda revisión tiene que usar V2 y c2"


# ---------------------------------------------------------------------------
# Chequeos de integración (requiere API)
# ---------------------------------------------------------------------------
def check_flujo_completo_con_api(generar_borrador, reflexionar_sobre_borrador, revisar_borrador):
    # requiere API
    consigna = "¿Cuáles son los beneficios de hacer ejercicio?"
    borrador = generar_borrador(consigna)
    assert isinstance(borrador, str) and len(borrador) > 100, "El borrador es muy corto o no es str"
    critica = reflexionar_sobre_borrador(borrador)
    assert isinstance(critica, str) and len(critica) > 50, "La crítica es muy corta o no es str"
    revision = revisar_borrador(borrador, critica)
    assert isinstance(revision, str) and len(revision) > 100, "La revisión es muy corta o no es str"
    assert revision.strip() != borrador.strip(), "La revisión salió idéntica al borrador"


# ---------------------------------------------------------------------------
# run_all: para llamar desde el notebook
# ---------------------------------------------------------------------------
def run_all(
    generar_borrador,
    reflexionar_sobre_borrador,
    revisar_borrador,
    reflexionar_en_bucle=None,
    client=None,
) -> tuple[int, int]:
    """Corre todos los chequeos e imprime un resumen. Devuelve (aprobados, total).

    Los estructurales corren siempre (sin API). Los de integración solo si `client`
    no es None.
    """
    todas = [generar_borrador, reflexionar_sobre_borrador, revisar_borrador, reflexionar_en_bucle]
    pruebas = [
        ("generar_borrador devuelve el texto del modelo y usa `model`",
         lambda: check_generar_borrador(generar_borrador, todas)),
        ("reflexionar_sobre_borrador recibe el borrador y devuelve la crítica",
         lambda: check_reflexionar_sobre_borrador(reflexionar_sobre_borrador, todas)),
        ("revisar_borrador recibe borrador + crítica y devuelve algo distinto",
         lambda: check_revisar_borrador(revisar_borrador, todas)),
    ]
    if reflexionar_en_bucle is not None:
        pruebas.append(("reflexionar_en_bucle encadena N rondas sobre el último borrador",
                        lambda: check_reflexionar_en_bucle(reflexionar_en_bucle, todas)))
    if client is not None:
        # requiere API
        pruebas.append(("flujo completo con la API real (3 llamadas)",
                        lambda: check_flujo_completo_con_api(generar_borrador, reflexionar_sobre_borrador, revisar_borrador)))

    aprobados = 0
    for nombre, prueba in pruebas:
        try:
            prueba()
            print(f"OK     {nombre}")
            aprobados += 1
        except AssertionError as e:
            print(f"FALLA  {nombre}\n       -> {e}")
        except NotImplementedError:
            print(f"FALLA  {nombre}\n       -> la función todavía tiene el placeholder NotImplementedError")
        except Exception as e:  # cualquier otro error del código del alumno
            print(f"ERROR  {nombre}\n       -> {type(e).__name__}: {e}")
    print(f"\n{aprobados}/{len(pruebas)} chequeos aprobados.")
    return aprobados, len(pruebas)


# ---------------------------------------------------------------------------
# Modo pytest: carga las funciones desde el notebook (nunca llama a la API)
# ---------------------------------------------------------------------------
def cargar_funciones_del_notebook(ruta: Path) -> dict:
    """Ejecuta solo las celdas que definen las funciones del lab, con un `client` falso."""
    nb = json.loads(ruta.read_text(encoding="utf-8"))
    patron = re.compile(r"^def (" + "|".join(FUNCIONES_DEL_LAB) + r")\(", re.MULTILINE)
    ns = {
        "client": FakeClient(),
        "MODEL_CHEAP": "modelo-barato", "MODEL_STRONG": "modelo-fuerte",
        "AI_CHEAP": "openai:modelo-barato", "AI_STRONG": "openai:modelo-fuerte",
    }
    for celda in nb["cells"]:
        if celda["cell_type"] != "code":
            continue
        codigo = "".join(celda["source"])
        if patron.search(codigo):
            exec(codigo, ns)
    faltan = [n for n in FUNCIONES_DEL_LAB if n not in ns]
    assert not faltan, f"No encontré en {ruta.name} las funciones: {faltan}"
    return ns


def _notebook_a_probar() -> Path | None:
    for nombre in ("notebook_solucion.ipynb", "notebook_alumno.ipynb"):
        if (AQUI / nombre).exists():
            return AQUI / nombre
    return None


_cache: dict = {}


def _funciones():
    if "ns" not in _cache:
        ruta = _notebook_a_probar()
        assert ruta is not None, "No hay notebook en la carpeta: corré tools/build_nb.py"
        _cache["ns"] = cargar_funciones_del_notebook(ruta)
    return _cache["ns"]


def test_fake_client_tiene_la_forma_del_sdk():
    fake = FakeClient(respuestas=["hola"])
    r = fake.chat.completions.create(model="openai:x", messages=[{"role": "user", "content": "¿qué tal?"}])
    assert r.choices[0].message.content == "hola"
    assert fake.ultimo_prompt == "¿qué tal?"
    assert fake.llamadas[0]["model"] == "openai:x"


def test_generar_borrador():
    ns = _funciones()
    check_generar_borrador(ns["generar_borrador"])


def test_reflexionar_sobre_borrador():
    ns = _funciones()
    check_reflexionar_sobre_borrador(ns["reflexionar_sobre_borrador"])


def test_revisar_borrador():
    ns = _funciones()
    check_revisar_borrador(ns["revisar_borrador"])


def test_reflexionar_en_bucle():
    ns = _funciones()
    check_reflexionar_en_bucle(ns["reflexionar_en_bucle"])

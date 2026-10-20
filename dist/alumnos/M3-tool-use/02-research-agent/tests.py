"""Tests del lab 02 que NO necesitan API: un cliente falso simula las respuestas del modelo.

Dos formas de usarlos:

1. Desde el notebook, después de completar cada hueco:

       from tests import run_all
       run_all(wikipedia_tool_def)          # chequea la forma del schema
       run_all(investigar_con_tools)        # chequea el loop con un cliente falso
       run_all(reflexionar_y_reescribir)
       run_all(convertir_a_html)

2. Con pytest, desde esta carpeta (lado docente: carga las funciones desde
   notebook_solucion.ipynb; si ese archivo no está, los tests se saltean):

       pytest -q

Qué verifican: que el loop agregue los mensajes "tool" con el tool_call_id
correcto, respete max_turns y no corte ante una tool que falla; que la reflexión
sean DOS llamadas y la segunda reciba la crítica; que la conversión a HTML quite
los fences y valide. Nada depende del texto exacto que devolvería un modelo real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

AQUI = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Cliente falso: imita client.chat.completions.create devolviendo respuestas en orden
# ---------------------------------------------------------------------------
def respuesta_texto(contenido: str):
    """Un response cuyo mensaje es texto final (sin tool_calls)."""
    msg = SimpleNamespace(role="assistant", content=contenido, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def respuesta_tool_calls(llamadas: list[tuple[str, str, dict]]):
    """Un response cuyo mensaje pide una o más tools. llamadas = [(id, nombre, args_dict), ...]."""
    calls = []
    for call_id, nombre, args in llamadas:
        calls.append(
            SimpleNamespace(
                id=call_id,
                type="function",
                function=SimpleNamespace(name=nombre, arguments=json.dumps(args)),
            )
        )
    msg = SimpleNamespace(role="assistant", content=None, tool_calls=calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeClient:
    """Devuelve las respuestas pre-armadas en orden y guarda los kwargs de cada llamada."""

    def __init__(self, respuestas: list):
        self._respuestas = list(respuestas)
        self.llamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # copiamos messages: el loop muta la misma lista entre llamadas
        snapshot = dict(kwargs)
        snapshot["messages"] = list(kwargs.get("messages", []))
        self.llamadas.append(snapshot)
        if not self._respuestas:
            raise AssertionError(
                f"El código llamó al modelo {len(self.llamadas)} veces, más de lo esperado. "
                "¿El loop corta cuando no hay tool_calls?"
            )
        return self._respuestas.pop(0)


def _con_cliente_falso(func, fake: FakeClient, tool_falsa=None):
    """Context manager: reemplaza `client` (y una tool del mapping) en los globals de func."""

    class _Ctx:
        def __enter__(self):
            g = func.__globals__
            self.g = g
            self.client_viejo = g.get("client", None)
            g["client"] = fake
            self.tool_vieja = None
            if tool_falsa is not None:
                if "tool_mapping" not in g:
                    raise AssertionError("Falta tool_mapping: ejecutá primero la celda de despacho (sección 4)")
                self.tool_vieja = g["tool_mapping"].get("arxiv_search_tool")
                g["tool_mapping"]["arxiv_search_tool"] = tool_falsa
            return self

        def __exit__(self, *exc):
            self.g["client"] = self.client_viejo
            if tool_falsa is not None:
                self.g["tool_mapping"]["arxiv_search_tool"] = self.tool_vieja
            return False

    return _Ctx()


def _mensajes_tool(messages: list) -> list[dict]:
    return [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]


# ---------------------------------------------------------------------------
# (b) wikipedia_tool_def: forma del schema
# ---------------------------------------------------------------------------
def check_schema_wikipedia(schema: dict):
    assert isinstance(schema, dict), "El schema tiene que ser un dict"
    assert schema.get("type") == "function", '"type" tiene que ser "function"'
    fn = schema.get("function", {})
    assert fn.get("name") == "wikipedia_search_tool", '"name" tiene que ser "wikipedia_search_tool" (la clave de tool_mapping)'
    assert fn.get("description", "").strip(), '"description" no puede estar vacía: es lo que lee el modelo'
    params = fn.get("parameters", {})
    assert params.get("type") == "object", '"parameters.type" tiene que ser "object"'
    props = params.get("properties", {})
    assert "query" in props, 'falta el parámetro "query" en properties'
    assert props["query"].get("type") == "string", '"query" tiene que ser de tipo string'
    assert props["query"].get("description", "").strip(), '"query" necesita una descripción'
    assert "query" in params.get("required", []), '"query" tiene que estar en "required" (no tiene default)'
    for nombre, prop in props.items():
        assert "type" in prop, f'el parámetro "{nombre}" no tiene "type"'
    # tiene que ser serializable: es lo que viaja a la API
    json.dumps(schema)


# ---------------------------------------------------------------------------
# (c) investigar_con_tools: el loop
# ---------------------------------------------------------------------------
def check_loop_sin_tools_devuelve_texto(func):
    fake = FakeClient([respuesta_texto("Informe directo.")])
    with _con_cliente_falso(func, fake):
        out = func("tema de prueba", max_turns=3)
    assert out == "Informe directo.", f"Tiene que devolver el content final; devolvió {out!r}"
    assert len(fake.llamadas) == 1, f"Sin tool_calls tiene que haber UNA llamada; hubo {len(fake.llamadas)}"
    kw = fake.llamadas[0]
    assert "tools" in kw and isinstance(kw["tools"], list) and kw["tools"], "La llamada tiene que llevar tools=[...schemas...]"
    assert kw["tools"][0].get("type") == "function", "tools tiene que ser una lista de schemas (dicts con type=function), no funciones"
    roles = [m.get("role") if isinstance(m, dict) else getattr(m, "role", None) for m in kw["messages"]]
    assert roles[0] == "system", "El primer mensaje tiene que ser el system prompt del investigador"
    assert "user" in roles, "Falta el mensaje user con el pedido"


def check_loop_ejecuta_tool_y_agrega_mensaje_tool(func):
    registro = {}

    def arxiv_falsa(query: str, max_results: int = 5):
        registro["args"] = {"query": query, "max_results": max_results}
        return [{"title": "Paper X", "url": "http://arxiv.org/abs/0000.0000", "snippet": "..."}]

    fake = FakeClient([
        respuesta_tool_calls([("call_abc", "arxiv_search_tool", {"query": "RAG", "max_results": 2})]),
        respuesta_texto("Informe final con fuentes."),
    ])
    with _con_cliente_falso(func, fake, tool_falsa=arxiv_falsa):
        out = func("tema de prueba", max_turns=4)

    assert out == "Informe final con fuentes.", f"Tiene que devolver el texto final; devolvió {out!r}"
    assert len(fake.llamadas) == 2, f"tool_call + respuesta final = 2 llamadas; hubo {len(fake.llamadas)}"
    assert registro.get("args") == {"query": "RAG", "max_results": 2}, (
        f"La tool tiene que ejecutarse con los argumentos del modelo (json.loads + **args); recibió {registro.get('args')}"
    )
    msgs = fake.llamadas[1]["messages"]
    tools_msgs = _mensajes_tool(msgs)
    assert len(tools_msgs) == 1, f"Tiene que haber exactamente un mensaje role=tool antes de la segunda llamada; hay {len(tools_msgs)}"
    t = tools_msgs[0]
    assert t.get("tool_call_id") == "call_abc", f'tool_call_id tiene que ser el id del call ("call_abc"); es {t.get("tool_call_id")!r}'
    assert isinstance(t.get("content"), str), "content del mensaje tool tiene que ser un string (json.dumps del resultado)"
    assert json.loads(t["content"]) == arxiv_falsa("RAG", 2), "content tiene que ser el resultado de la tool serializado"
    # el mensaje del modelo (con tool_calls) tiene que ir ANTES del mensaje tool
    idx_tool = msgs.index(t)
    anterior = msgs[idx_tool - 1]
    assert getattr(anterior, "tool_calls", None), "Antes del mensaje tool tiene que estar el mensaje del modelo que pidió la tool"


def check_loop_dos_tool_calls_en_un_turno(func):
    def arxiv_falsa(query: str, max_results: int = 5):
        return [{"title": f"resultado para {query}"}]

    fake = FakeClient([
        respuesta_tool_calls([
            ("call_1", "arxiv_search_tool", {"query": "A"}),
            ("call_2", "arxiv_search_tool", {"query": "B"}),
        ]),
        respuesta_texto("Listo."),
    ])
    with _con_cliente_falso(func, fake, tool_falsa=arxiv_falsa):
        func("tema", max_turns=3)
    ids = [m["tool_call_id"] for m in _mensajes_tool(fake.llamadas[1]["messages"])]
    assert ids == ["call_1", "call_2"], f"Con dos tool_calls en un turno tiene que haber dos mensajes tool, en orden; hay {ids}"


def check_loop_tool_que_falla_no_corta(func):
    def arxiv_rota(query: str, max_results: int = 5):
        raise ConnectionError("sin internet")

    fake = FakeClient([
        respuesta_tool_calls([("call_err", "arxiv_search_tool", {"query": "X"})]),
        respuesta_texto("Informe sin esa fuente."),
    ])
    with _con_cliente_falso(func, fake, tool_falsa=arxiv_rota):
        out = func("tema", max_turns=3)
    assert out == "Informe sin esa fuente.", "Si una tool falla, el loop tiene que seguir y devolverle el error al modelo"
    t = _mensajes_tool(fake.llamadas[1]["messages"])[0]
    contenido = json.loads(t["content"])
    assert isinstance(contenido, dict) and "error" in contenido, f'El resultado de una tool rota tiene que ser {{"error": ...}}; fue {contenido!r}'


def check_loop_respeta_max_turns(func):
    def arxiv_falsa(query: str, max_results: int = 5):
        return []

    fake = FakeClient([respuesta_tool_calls([(f"call_{i}", "arxiv_search_tool", {"query": "X"})]) for i in range(5)])
    with _con_cliente_falso(func, fake, tool_falsa=arxiv_falsa):
        try:
            func("tema", max_turns=2)
        except NotImplementedError:
            raise  # hueco sin completar: que run_all lo informe como FALTA
        except RuntimeError:
            pass
        else:
            raise AssertionError("Si se agotan los turnos sin respuesta final tiene que levantar RuntimeError")
    assert len(fake.llamadas) == 2, f"Con max_turns=2 tiene que haber exactamente 2 llamadas; hubo {len(fake.llamadas)}"


# ---------------------------------------------------------------------------
# (d) reflexionar_y_reescribir: dos llamadas
# ---------------------------------------------------------------------------
def check_reflexion_dos_llamadas(func):
    fake = FakeClient([respuesta_texto("CRÍTICA: faltan fuentes."), respuesta_texto("INFORME REVISADO con fuentes.")])
    with _con_cliente_falso(func, fake):
        out = func("Informe original sobre RAG.")
    assert isinstance(out, dict), "Tiene que devolver un dict"
    assert set(out) == {"critica", "informe_revisado"}, f"Las claves tienen que ser critica e informe_revisado; son {set(out)}"
    assert out["critica"] == "CRÍTICA: faltan fuentes.", "critica tiene que ser lo que devolvió la PRIMERA llamada"
    assert out["informe_revisado"] == "INFORME REVISADO con fuentes.", "informe_revisado tiene que ser lo que devolvió la SEGUNDA llamada"
    assert out["critica"] != out["informe_revisado"], "Crítica y reescritura no pueden ser el mismo texto (eso hacía el original)"
    assert len(fake.llamadas) == 2, f"Tienen que ser DOS llamadas separadas; hubo {len(fake.llamadas)}"

    def texto_de(llamada):
        return " ".join(str(m.get("content", "")) if isinstance(m, dict) else str(getattr(m, "content", "")) for m in llamada["messages"])

    assert "Informe original sobre RAG." in texto_de(fake.llamadas[0]), "La primera llamada tiene que incluir el informe"
    assert "CRÍTICA: faltan fuentes." in texto_de(fake.llamadas[1]), "La segunda llamada tiene que recibir la crítica de la primera"
    assert "Informe original sobre RAG." in texto_de(fake.llamadas[1]), "La segunda llamada también necesita el informe original"


def check_reflexion_informe_vacio(func):
    fake = FakeClient([])
    with _con_cliente_falso(func, fake):
        try:
            func("   ")
        except ValueError:
            pass
        else:
            raise AssertionError("Con un informe vacío tiene que levantar ValueError sin llamar al modelo")
    assert fake.llamadas == [], "Con informe vacío no hay que llamar al modelo"


# ---------------------------------------------------------------------------
# (e) convertir_a_html: fences y validación
# ---------------------------------------------------------------------------
def check_html_quita_fences(func):
    fake = FakeClient([respuesta_texto("```html\n<html><body><h1>Hola</h1></body></html>\n```")])
    with _con_cliente_falso(func, fake):
        out = func("Informe de prueba.")
    assert isinstance(out, str) and out.startswith("<html"), f"Tiene que devolver el HTML sin fences; empieza así: {out[:30]!r}"
    assert "```" not in out, "Quedaron fences ``` en el HTML"
    assert out.endswith("</html>"), f"El cierre también tiene que quedar limpio; termina así: {out[-20:]!r}"
    assert len(fake.llamadas) == 1


def check_html_sin_fences_queda_igual(func):
    fake = FakeClient([respuesta_texto("<p>ok</p>")])
    with _con_cliente_falso(func, fake):
        out = func("Informe de prueba.")
    assert out == "<p>ok</p>"


def check_html_valida_que_sea_html(func):
    fake = FakeClient([respuesta_texto("No puedo convertir eso.")])
    with _con_cliente_falso(func, fake):
        try:
            func("Informe de prueba.")
        except ValueError:
            pass
        else:
            raise AssertionError("Si el modelo no devuelve HTML tiene que levantar ValueError")


def check_html_informe_vacio(func):
    fake = FakeClient([])
    with _con_cliente_falso(func, fake):
        try:
            func("")
        except ValueError:
            pass
        else:
            raise AssertionError("Con un informe vacío tiene que levantar ValueError sin llamar al modelo")
    assert fake.llamadas == []


# ---------------------------------------------------------------------------
# run_all: desde el notebook
# ---------------------------------------------------------------------------
CHECKS = {
    "investigar_con_tools": [
        check_loop_sin_tools_devuelve_texto,
        check_loop_ejecuta_tool_y_agrega_mensaje_tool,
        check_loop_dos_tool_calls_en_un_turno,
        check_loop_tool_que_falla_no_corta,
        check_loop_respeta_max_turns,
    ],
    "reflexionar_y_reescribir": [check_reflexion_dos_llamadas, check_reflexion_informe_vacio],
    "convertir_a_html": [check_html_quita_fences, check_html_sin_fences_queda_igual, check_html_valida_que_sea_html, check_html_informe_vacio],
}


def run_all(objetivo) -> bool:
    """Corre los chequeos que corresponden a una función (o al dict wikipedia_tool_def). Imprime OK/FALLA."""
    if isinstance(objetivo, dict):
        checks = [check_schema_wikipedia]
        nombre = "wikipedia_tool_def"
    else:
        nombre = getattr(objetivo, "__name__", "")
        if nombre not in CHECKS:
            raise ValueError(f"No tengo tests para {nombre!r}. Opciones: {list(CHECKS)} o el dict wikipedia_tool_def")
        checks = CHECKS[nombre]

    fallas = 0
    for check in checks:
        try:
            check(objetivo)
            print(f"OK     {check.__name__}")
        except NotImplementedError:
            print(f"FALTA  {check.__name__}: todavía hay un hueco sin completar")
            fallas += 1
        except AssertionError as e:
            print(f"FALLA  {check.__name__}: {e}")
            fallas += 1
        except Exception as e:  # error de programación en la función del alumno
            print(f"ERROR  {check.__name__}: {type(e).__name__}: {e}")
            fallas += 1
    print(f"{nombre}: {'todo OK' if fallas == 0 else f'{fallas} chequeo(s) fallaron'}")
    return fallas == 0


# ---------------------------------------------------------------------------
# pytest: carga las definiciones desde notebook_solucion.ipynb (lado docente)
# ---------------------------------------------------------------------------
_PREFIJOS = ("arxiv_tool_def =", "wikipedia_tool_def =", "TOOL_DEFS =", "SYSTEM_INVESTIGADOR =", "PROMPT_CRITICA =", "PROMPT_HTML =", "def ")
_NS: dict | None = None


def _namespace_solucion() -> dict:
    """Ejecuta solo las celdas de definición del notebook solución, con un client falso."""
    global _NS
    if _NS is not None:
        return _NS
    import pytest

    nb_path = AQUI / "notebook_solucion.ipynb"
    if not nb_path.exists():
        pytest.skip("No está notebook_solucion.ipynb: estos tests se corren desde el notebook con run_all(...)")
    import nbformat

    if str(AQUI) not in sys.path:
        sys.path.insert(0, str(AQUI))
    import research_tools

    ns = {
        "json": json,
        "client": None,
        "MODEL_CHEAP": "modelo-barato-falso",
        "MODEL_STRONG": "modelo-fuerte-falso",
        "research_tools": research_tools,
    }
    nb = nbformat.read(nb_path, as_version=4)
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        lineas = [l for l in cell.source.splitlines() if l.strip() and not l.strip().startswith("#")]
        if not lineas:
            continue
        if lineas[0].startswith(_PREFIJOS):
            exec(compile(cell.source, "notebook_solucion", "exec"), ns)
    _NS = ns
    return ns


def _f(nombre):
    ns = _namespace_solucion()
    assert nombre in ns, f"No encontré {nombre} en el notebook solución"
    return ns[nombre]


def test_schema_wikipedia():
    check_schema_wikipedia(_f("wikipedia_tool_def"))


def test_loop_sin_tools_devuelve_texto():
    check_loop_sin_tools_devuelve_texto(_f("investigar_con_tools"))


def test_loop_ejecuta_tool_y_agrega_mensaje_tool():
    check_loop_ejecuta_tool_y_agrega_mensaje_tool(_f("investigar_con_tools"))


def test_loop_dos_tool_calls_en_un_turno():
    check_loop_dos_tool_calls_en_un_turno(_f("investigar_con_tools"))


def test_loop_tool_que_falla_no_corta():
    check_loop_tool_que_falla_no_corta(_f("investigar_con_tools"))


def test_loop_respeta_max_turns():
    check_loop_respeta_max_turns(_f("investigar_con_tools"))


def test_reflexion_dos_llamadas():
    check_reflexion_dos_llamadas(_f("reflexionar_y_reescribir"))


def test_reflexion_informe_vacio():
    check_reflexion_informe_vacio(_f("reflexionar_y_reescribir"))


def test_html_quita_fences():
    check_html_quita_fences(_f("convertir_a_html"))


def test_html_sin_fences_queda_igual():
    check_html_sin_fences_queda_igual(_f("convertir_a_html"))


def test_html_valida_que_sea_html():
    check_html_valida_que_sea_html(_f("convertir_a_html"))


def test_html_informe_vacio():
    check_html_informe_vacio(_f("convertir_a_html"))


def test_quitar_fences_helper():
    quitar = _f("quitar_fences")
    assert quitar("```html\n<p>a</p>\n```") == "<p>a</p>"
    assert quitar("```\n<p>a</p>```") == "<p>a</p>"
    assert quitar("<p>a</p>") == "<p>a</p>"

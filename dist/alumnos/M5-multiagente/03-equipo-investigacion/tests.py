"""Tests del lab 03 (M5): planner, executor y helpers, con un cliente aisuite simulado. Sin API.

Correr: ``pytest -q`` dentro de esta carpeta.
Desde el notebook, al final:

    from tests import run_all
    run_all(agente_planner, agente_executor, registro_agentes, namespace=globals())

``run_all`` reemplaza temporalmente ``client`` del notebook por un ``FakeClient`` y los
agentes del registro por funciones de prueba, así los tests del alumno no gastan llamadas.
"""
from __future__ import annotations

import json
from typing import Any, Callable

import pytest

import research_tools
import utils

# ---------------------------------------------------------------------------
# Cliente aisuite simulado (misma forma: response.choices[0].message.content
# y response.choices[0].intermediate_messages)
# ---------------------------------------------------------------------------


class _Msg:
    def __init__(self, content):
        self.content = content
        self.role = "assistant"


class _Choice:
    def __init__(self, content, intermedios=None):
        self.message = _Msg(content)
        self.intermediate_messages = intermedios or []


class FakeResponse:
    def __init__(self, content, intermedios=None):
        self.choices = [_Choice(content, intermedios)]


class FakeClient:
    """Devuelve ``respuestas`` en orden (o lo que decida ``responder(kwargs)``) y registra las llamadas."""

    def __init__(self, respuestas: list[str] | None = None, responder: Callable[[dict], str] | None = None):
        self.respuestas = list(respuestas or [])
        self.responder = responder
        self.llamadas: list[dict[str, Any]] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        if self.responder is not None:
            return FakeResponse(self.responder(kwargs))
        if not self.respuestas:
            raise AssertionError("FakeClient se quedó sin respuestas: el código hizo más llamadas de las esperadas")
        return FakeResponse(self.respuestas.pop(0))


def rutear_por_palabras(kwargs: dict) -> str:
    """Router simulado: decide por palabras clave de la instrucción y devuelve el JSON con fences."""
    texto = kwargs["messages"][-1]["content"]
    instr = texto.split('Instrucción: "')[1].rstrip().rstrip('"') if 'Instrucción: "' in texto else texto
    bajo = instr.lower()
    if "buscar" in bajo:
        agente = "agente_research"
    elif "revisar" in bajo:
        agente = "agente_editor"
    else:
        agente = "agente_writer"
    return "```json\n" + json.dumps({"agente": agente, "tarea": "LIMPIA: " + instr}) + "\n```"


# ---------------------------------------------------------------------------
# Implementaciones de referencia (misma lógica que la solución del notebook)
# ---------------------------------------------------------------------------

_CLIENTE_REF = FakeClient()

registro_de_prueba: dict[str, Callable[[str], str]] = {
    "agente_research": lambda tarea: f"RESEARCH({len(tarea)})",
    "agente_writer": lambda tarea: f"WRITER({len(tarea)})",
    "agente_editor": lambda tarea: f"EDITOR({len(tarea)})",
}


def _planner_referencia(tema: str, model: str = "openai:x") -> list[str]:
    response = _CLIENTE_REF.chat.completions.create(model=model, messages=[{"role": "user", "content": f"agente planificador {tema}"}])
    pasos = json.loads(utils.limpiar_json(response.choices[0].message.content))
    if not isinstance(pasos, list) or not pasos:
        raise ValueError("El planner tenía que devolver una lista JSON no vacía.")
    for i, p in enumerate(pasos, start=1):
        if not isinstance(p, str) or not p.strip():
            raise ValueError(f"El paso {i} del plan no es un texto: {p!r}")
    return [p.strip() for p in pasos]


def _armar_contexto(historial):
    if not historial:
        return "(todavía no se ejecutó ningún paso)"
    return "\n\n".join(f"### Paso {i} — hecho por {a}\nTarea: {p}\nResultado:\n{s}" for i, (p, a, s) in enumerate(historial, start=1))


def _executor_referencia(pasos: list[str], model: str = "openai:x", registro=None) -> list[tuple[str, str, str]]:
    registro = registro if registro is not None else registro_de_prueba
    historial = []
    for i, paso in enumerate(pasos, start=1):
        response = _CLIENTE_REF.chat.completions.create(model=model, messages=[{"role": "user", "content": f'coordinador\nInstrucción: "{paso}"\n'}])
        decision = json.loads(utils.limpiar_json(response.choices[0].message.content))
        agente, tarea = decision.get("agente"), decision.get("tarea")
        if agente not in registro:
            raise ValueError(f"El router eligió un agente desconocido: {agente!r}.")
        if not isinstance(tarea, str) or not tarea.strip():
            raise ValueError("tarea vacía")
        enriquecida = f"Sos {agente}.\n\n## Contexto de lo hecho hasta ahora\n{_armar_contexto(historial)}\n\n## Tu tarea ahora\n{tarea}"
        salida = registro[agente](enriquecida)
        historial.append((paso, agente, salida))
    return historial


# Lo que se testea. pytest usa las referencias; run_all las reemplaza por las del alumno.
PLANNER: Callable = _planner_referencia
EXECUTOR: Callable = _executor_referencia
_NAMESPACE: dict | None = None      # globals() del notebook, para inyectar el FakeClient
_REGISTRO: dict | None = None       # registro_agentes del notebook, para inyectar agentes de prueba


def _con_cliente(fake: FakeClient):
    """Hace que la función bajo prueba use `fake` como cliente. Devuelve una función para restaurar."""
    global _CLIENTE_REF
    anterior_ref = _CLIENTE_REF
    _CLIENTE_REF = fake
    anterior_ns = None
    anterior_reg = None
    if _NAMESPACE is not None:
        anterior_ns = _NAMESPACE.get("client")
        _NAMESPACE["client"] = fake
    if _REGISTRO is not None:
        anterior_reg = dict(_REGISTRO)
        _REGISTRO.clear()
        _REGISTRO.update(registro_de_prueba)

    def restaurar():
        global _CLIENTE_REF
        _CLIENTE_REF = anterior_ref
        if _NAMESPACE is not None:
            _NAMESPACE["client"] = anterior_ns
        if _REGISTRO is not None and anterior_reg is not None:
            _REGISTRO.clear()
            _REGISTRO.update(anterior_reg)

    return restaurar


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------


def test_limpiar_json_quita_fences_y_texto_alrededor():
    assert utils.limpiar_json('["a", "b"]') == '["a", "b"]'
    assert utils.limpiar_json('```json\n["a", "b"]\n```') == '["a", "b"]'
    assert utils.limpiar_json('```\n{"agente": "x"}\n```') == '{"agente": "x"}'
    assert utils.limpiar_json('Acá va:\n["a"]\nListo.') == '["a"]'
    assert json.loads(utils.limpiar_json('```json\n{"t": "con [corchetes] adentro"}\n```')) == {"t": "con [corchetes] adentro"}


def test_limpiar_json_errores_en_espanol():
    with pytest.raises(ValueError, match="vacía"):
        utils.limpiar_json("   ")
    with pytest.raises(ValueError, match="No encontré"):
        utils.limpiar_json("no hay nada parecido a json")
    with pytest.raises(ValueError, match="no cierra"):
        utils.limpiar_json("[1, 2")


def test_quitar_fences_y_guardar_informe(tmp_path):
    assert utils.quitar_fences("```markdown\n# T\n\ntexto\n```") == "# T\n\ntexto"
    assert utils.quitar_fences("# T") == "# T"
    ruta = utils.guardar_informe("# Informe\n", tmp_path / "sub" / "informe.md")
    assert ruta.exists() and ruta.read_text(encoding="utf-8") == "# Informe\n"


def test_tool_mapping_usa_los_nombres_reales_de_las_funciones():
    """El system prompt del Research tiene que nombrar las tools como se llaman de verdad."""
    for nombre, fn in research_tools.tool_mapping.items():
        assert fn.__name__ == nombre
    assert set(research_tools.tool_mapping) == {"arxiv_search_tool", "tavily_search_tool", "wikipedia_search_tool"}


def test_parse_arxiv_feed_offline():
    xml = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
    <entry><id>http://arxiv.org/abs/1234.5678v1</id><title>  Un  título\n largo </title>
    <summary>Resumen  del paper.</summary><published>2024-01-02T00:00:00Z</published>
    <author><name>Ana</name></author><author><name>Beto</name></author></entry></feed>"""
    papers = research_tools.parse_arxiv_feed(xml)
    assert papers == [{"title": "Un título largo", "authors": ["Ana", "Beto"], "published": "2024-01-02",
                       "snippet": "Resumen del paper.", "url": "http://arxiv.org/abs/1234.5678v1"}]


# ---------------------------------------------------------------------------
# planner
# ---------------------------------------------------------------------------


def test_planner_parsea_lista_con_fences():
    fake = FakeClient(['```json\n["Buscar A", "Redactar B", "Redactar el informe en Markdown"]\n```'])
    restaurar = _con_cliente(fake)
    try:
        pasos = PLANNER("tema de prueba")
    finally:
        restaurar()
    assert pasos == ["Buscar A", "Redactar B", "Redactar el informe en Markdown"]
    assert len(fake.llamadas) == 1
    assert "tema de prueba" in fake.llamadas[0]["messages"][-1]["content"]


def test_planner_parsea_lista_limpia_y_con_texto_alrededor():
    fake = FakeClient(['Acá está el plan:\n["uno", "dos"]\nEspero que sirva.'])
    restaurar = _con_cliente(fake)
    try:
        assert PLANNER("x") == ["uno", "dos"]
    finally:
        restaurar()


def test_planner_rechaza_lo_que_no_es_lista_de_strings():
    for malo in ['{"a": 1}', "[]", '["ok", 3]', "texto sin json"]:
        fake = FakeClient([malo])
        restaurar = _con_cliente(fake)
        try:
            with pytest.raises(ValueError):
                PLANNER("x")
        finally:
            restaurar()


# ---------------------------------------------------------------------------
# executor
# ---------------------------------------------------------------------------

PLAN_PRUEBA = ["Buscar en arXiv papers sobre X", "Redactar un resumen", "Revisar el resumen", "Redactar el informe en Markdown"]


def test_executor_rutea_y_devuelve_historial_con_forma_correcta():
    fake = FakeClient(responder=rutear_por_palabras)
    restaurar = _con_cliente(fake)
    try:
        historial = EXECUTOR(PLAN_PRUEBA)
    finally:
        restaurar()
    assert isinstance(historial, list) and len(historial) == 4
    for item in historial:
        assert isinstance(item, tuple) and len(item) == 3
        assert all(isinstance(x, str) for x in item)
    assert [paso for paso, _, _ in historial] == PLAN_PRUEBA
    assert [agente for _, agente, _ in historial] == ["agente_research", "agente_writer", "agente_editor", "agente_writer"]
    assert historial[0][2].startswith("RESEARCH(") and historial[2][2].startswith("EDITOR(")
    assert len(fake.llamadas) == 4, "una llamada de ruteo por paso (los agentes de prueba no llaman al modelo)"


def test_executor_pasa_el_historial_como_contexto():
    """La tarea que recibe el agente del paso 2 tiene que incluir la salida del paso 1."""
    recibidas: list[str] = []
    registro = {
        "agente_research": lambda t: (recibidas.append(t), "HALLAZGO-UNICO-123")[1],
        "agente_writer": lambda t: (recibidas.append(t), "borrador")[1],
        "agente_editor": lambda t: (recibidas.append(t), "ok")[1],
    }
    fake = FakeClient(responder=rutear_por_palabras)
    restaurar = _con_cliente(fake)
    if _REGISTRO is not None:
        _REGISTRO.clear()
        _REGISTRO.update(registro)
    try:
        if _REGISTRO is not None:
            EXECUTOR(["Buscar A", "Redactar B"])
        else:
            EXECUTOR(["Buscar A", "Redactar B"], registro=registro)
    finally:
        restaurar()
    assert len(recibidas) == 2
    assert "HALLAZGO-UNICO-123" not in recibidas[0]
    assert "HALLAZGO-UNICO-123" in recibidas[1]
    assert "LIMPIA: Redactar B" in recibidas[1]


def test_executor_agente_desconocido_levanta_valueerror():
    fake = FakeClient(['{"agente": "agente_fantasma", "tarea": "algo"}'])
    restaurar = _con_cliente(fake)
    try:
        with pytest.raises(ValueError, match="agente_fantasma"):
            EXECUTOR(["Hacer algo"])
    finally:
        restaurar()


def test_executor_json_roto_levanta_valueerror():
    fake = FakeClient(["no te voy a dar json"])
    restaurar = _con_cliente(fake)
    try:
        with pytest.raises(ValueError):
            EXECUTOR(["Hacer algo"])
    finally:
        restaurar()


def test_executor_plan_vacio_devuelve_historial_vacio():
    fake = FakeClient([])
    restaurar = _con_cliente(fake)
    try:
        assert EXECUTOR([]) == []
    finally:
        restaurar()


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------


def run_all(agente_planner=None, agente_executor=None, registro_agentes=None, namespace=None) -> None:
    """Corre todos los tests. Desde el notebook:

        run_all(agente_planner, agente_executor, registro_agentes, namespace=globals())

    ``namespace`` hace falta para reemplazar el ``client`` real por el simulado mientras
    corren los tests (no se gasta ninguna llamada). Se restaura al terminar cada test.
    """
    global PLANNER, EXECUTOR, _NAMESPACE, _REGISTRO
    if agente_planner is not None:
        PLANNER = agente_planner
    if agente_executor is not None:
        EXECUTOR = agente_executor
    if registro_agentes is not None:
        _REGISTRO = registro_agentes
    if namespace is not None:
        _NAMESPACE = namespace
    elif agente_planner is not None or agente_executor is not None:
        print("AVISO: pasá namespace=globals() para que los tests usen el cliente simulado en tus funciones.")

    import tempfile
    from pathlib import Path

    pruebas = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fallas = 0
    for prueba in pruebas:
        params = prueba.__code__.co_varnames[: prueba.__code__.co_argcount]
        try:
            if "tmp_path" in params:
                prueba(Path(tempfile.mkdtemp()))
            else:
                prueba()
            print(f"OK    {prueba.__name__}")
        except AssertionError as e:
            fallas += 1
            print(f"FALLA {prueba.__name__}: {e}")
        except Exception as e:
            fallas += 1
            print(f"ERROR {prueba.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(pruebas) - fallas}/{len(pruebas)} tests pasaron.")

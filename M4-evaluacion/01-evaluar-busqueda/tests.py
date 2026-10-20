"""Tests del lab 01 de M4: las cuatro funciones puras de la evaluación (sin API).

Dos formas de correrlos:

1. Desde el notebook, con las funciones que escribiste:

       from tests import run_all
       run_all(extraer_urls, dominio_de, es_dominio_confiable, evaluar_referencias)

2. Con ``pytest -q`` en esta carpeta. En ese caso las funciones se cargan desde la
   solución de ``lab.py`` (si el archivo no está, los tests se saltean con un aviso:
   usá ``run_all`` desde el notebook).

Ninguno de estos tests llama a la API: ``buscar_referencias`` y ``correr_evaluacion``
se prueban a mano en el notebook porque su salida depende del modelo.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

# Funciones bajo prueba. Las llena run_all (notebook) o _cargar_desde_lab (pytest).
FUNCS: dict = {}
NOMBRES = ("extraer_urls", "dominio_de", "es_dominio_confiable", "evaluar_referencias")


# ---------------------------------------------------------------------------
# Carga de las funciones
# ---------------------------------------------------------------------------
def _solo_solucion(codigo: str) -> str:
    """Quita los marcadores BEGIN/END SOLUTION y las líneas STUDENT (misma regla que build_nb.py)."""
    salida = []
    for linea in codigo.splitlines():
        s = linea.strip()
        if s in ("### BEGIN SOLUTION", "### END SOLUTION") or s.startswith("### STUDENT:"):
            continue
        salida.append(linea)
    return "\n".join(salida)


def _cargar_desde_lab() -> None:
    """Ejecuta solo las celdas de lab.py que definen las cuatro funciones puras."""
    lab = Path(__file__).with_name("lab.py")
    if not lab.exists():
        pytest.skip("No está lab.py: corré run_all(...) desde el notebook para probar tus funciones")
    texto = lab.read_text(encoding="utf-8")
    celdas = re.split(r"^# %%.*$", texto, flags=re.MULTILINE)
    espacio = {"re": re, "urlparse": urlparse}
    for celda in celdas:
        for nombre in NOMBRES:
            if f"def {nombre}(" in celda:
                exec(_solo_solucion(celda), espacio)
    for nombre in NOMBRES:
        if nombre not in espacio:
            pytest.skip(f"No encontré `def {nombre}(` en lab.py")
        FUNCS[nombre] = espacio[nombre]


def _fn(nombre: str):
    if nombre not in FUNCS:
        _cargar_desde_lab()
    return FUNCS[nombre]


# ---------------------------------------------------------------------------
# extraer_urls
# ---------------------------------------------------------------------------
def test_extraer_urls_basico():
    f = _fn("extraer_urls")
    assert f("mirá https://arxiv.org/abs/1 y http://nasa.gov/x") == ["https://arxiv.org/abs/1", "http://nasa.gov/x"]


def test_extraer_urls_devuelve_lista_de_strings():
    f = _fn("extraer_urls")
    r = f("https://a.org/b")
    assert isinstance(r, list), "tiene que devolver una lista"
    assert all(isinstance(u, str) for u in r)


def test_extraer_urls_sin_urls():
    assert _fn("extraer_urls")("acá no hay ningún link") == []


def test_extraer_urls_sin_duplicados_y_en_orden():
    f = _fn("extraer_urls")
    texto = "1) https://b.org/x  2) https://a.org/y  3) https://b.org/x otra vez"
    assert f(texto) == ["https://b.org/x", "https://a.org/y"], "sin duplicados y conservando el orden de aparición"


def test_extraer_urls_markdown_y_parentesis_final():
    f = _fn("extraer_urls")
    # el `)` que cierra el link de Markdown y el que cierra el paréntesis NO son parte de la URL
    texto = "[paper](https://arxiv.org/abs/1706.03762) y después (ver https://nasa.gov/mission)."
    assert f(texto) == ["https://arxiv.org/abs/1706.03762", "https://nasa.gov/mission"]


def test_extraer_urls_puntuacion_pegada():
    f = _fn("extraer_urls")
    assert f("Fuente: https://nature.com/articles/abc. Otra: https://acm.org/x, y fin") == [
        "https://nature.com/articles/abc",
        "https://acm.org/x",
    ]


def test_extraer_urls_entre_comillas_y_angulares():
    f = _fn("extraer_urls")
    assert f('<https://ieee.org/a> y "https://acm.org/b"') == ["https://ieee.org/a", "https://acm.org/b"]


# ---------------------------------------------------------------------------
# dominio_de
# ---------------------------------------------------------------------------
def test_dominio_de_simple():
    assert _fn("dominio_de")("https://arxiv.org/abs/1706.03762") == "arxiv.org"


def test_dominio_de_saca_www():
    assert _fn("dominio_de")("https://www.nature.com/articles/abc") == "nature.com"


def test_dominio_de_conserva_otros_subdominios():
    assert _fn("dominio_de")("https://en.wikipedia.org/wiki/Black_hole") == "en.wikipedia.org"


def test_dominio_de_minusculas():
    assert _fn("dominio_de")("https://WWW.NASA.GOV/mission") == "nasa.gov"


def test_dominio_de_con_puerto_y_http():
    # netloc incluye el puerto; lo dejamos tal cual (no es un caso que aparezca con fuentes reales)
    assert _fn("dominio_de")("http://localhost:8000/docs") == "localhost:8000"


# ---------------------------------------------------------------------------
# es_dominio_confiable
# ---------------------------------------------------------------------------
CONF = {"arxiv.org", "wikipedia.org", "mit.edu", "nature.com"}


def test_confiable_exacto():
    assert _fn("es_dominio_confiable")("arxiv.org", CONF) is True


def test_confiable_subdominio():
    f = _fn("es_dominio_confiable")
    assert f("en.wikipedia.org", CONF) is True
    assert f("web.mit.edu", CONF) is True


def test_confiable_no_confunde_substring():
    """El bug del original: 'mit.edu' in 'summit.edu' daba True."""
    f = _fn("es_dominio_confiable")
    assert f("summit.edu", CONF) is False
    assert f("notnature.com", CONF) is False


def test_confiable_no_confunde_prefijo():
    assert _fn("es_dominio_confiable")("arxiv.org.evil.com", CONF) is False


def test_confiable_vacio_y_mayusculas():
    f = _fn("es_dominio_confiable")
    assert f("", CONF) is False
    assert f("ARXIV.ORG", CONF) is True
    assert f("arxiv.org", set()) is False


# ---------------------------------------------------------------------------
# evaluar_referencias
# ---------------------------------------------------------------------------
TEXTO = """
- https://arxiv.org/abs/1706.03762
- https://en.wikipedia.org/wiki/Transformer
- https://towardsdatascience.com/post
- https://arxiv.org/abs/1706.03762  (repetida)
"""


def test_evaluar_claves_y_tipos():
    r = _fn("evaluar_referencias")(TEXTO, {"arxiv.org", "wikipedia.org"})
    assert set(r) >= {"total", "confiables", "ratio", "aprobado", "detalle"}, f"faltan claves: {r.keys()}"
    assert isinstance(r["total"], int) and isinstance(r["confiables"], int)
    assert isinstance(r["ratio"], float) and isinstance(r["aprobado"], bool)
    assert isinstance(r["detalle"], list)


def test_evaluar_cuenta_sin_duplicados():
    r = _fn("evaluar_referencias")(TEXTO, {"arxiv.org", "wikipedia.org"}, umbral=0.4)
    assert r["total"] == 3, "la URL repetida se cuenta una sola vez"
    assert r["confiables"] == 2
    assert abs(r["ratio"] - 2 / 3) < 1e-9
    assert r["aprobado"] is True


def test_evaluar_detalle_es_lista_de_tuplas_en_orden():
    r = _fn("evaluar_referencias")(TEXTO, {"arxiv.org", "wikipedia.org"})
    assert len(r["detalle"]) == 3
    url, dominio, ok = r["detalle"][0]
    assert url == "https://arxiv.org/abs/1706.03762" and dominio == "arxiv.org" and ok is True
    assert r["detalle"][2] == ("https://towardsdatascience.com/post", "towardsdatascience.com", False)


def test_evaluar_umbral_falla():
    r = _fn("evaluar_referencias")(TEXTO, {"arxiv.org", "wikipedia.org"}, umbral=0.7)
    assert r["aprobado"] is False, "2/3 = 0.67 no alcanza el umbral 0.7"


def test_evaluar_umbral_exacto_aprueba():
    r = _fn("evaluar_referencias")("https://a.org https://b.org", {"a.org"}, umbral=0.5)
    assert r["aprobado"] is True, "ratio == umbral tiene que aprobar (>=)"


def test_evaluar_sin_urls_no_divide_por_cero_y_falla():
    r = _fn("evaluar_referencias")("texto sin links", {"arxiv.org"}, umbral=0.0)
    assert r["total"] == 0 and r["ratio"] == 0.0
    assert r["aprobado"] is False, "sin URLs no puede aprobar, ni con umbral 0"
    assert r["detalle"] == []


def test_evaluar_texto_de_error_del_modelo():
    r = _fn("evaluar_referencias")("[Error en la búsqueda: timeout]", {"arxiv.org"})
    assert r["aprobado"] is False and r["total"] == 0


# ---------------------------------------------------------------------------
# run_all: para llamar desde el notebook
# ---------------------------------------------------------------------------
def run_all(extraer_urls=None, dominio_de=None, es_dominio_confiable=None, evaluar_referencias=None) -> bool:
    """Corre todos los tests con las funciones que le pasás. Imprime un resumen y devuelve True si pasaron todos."""
    recibidas = {
        "extraer_urls": extraer_urls,
        "dominio_de": dominio_de,
        "es_dominio_confiable": es_dominio_confiable,
        "evaluar_referencias": evaluar_referencias,
    }
    for nombre, fn in recibidas.items():
        if fn is not None:
            FUNCS[nombre] = fn

    import traceback

    tests = [(n, obj) for n, obj in sorted(globals().items()) if n.startswith("test_") and callable(obj)]
    ok = 0
    for nombre, test in tests:
        try:
            test()
            print(f"OK     {nombre}")
            ok += 1
        except NotImplementedError:
            print(f"FALTA  {nombre}: la función todavía tiene el placeholder NotImplementedError")
        except AssertionError as e:
            # si el assert no tiene mensaje, mostramos la línea que falló
            detalle = str(e).strip() or traceback.extract_tb(e.__traceback__)[-1].line
            print(f"FALLA  {nombre}: {detalle}")
        except Exception as e:  # noqa: BLE001 - queremos mostrar cualquier fallo
            print(f"ERROR  {nombre}: {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(tests)} tests pasaron")
    return ok == len(tests)

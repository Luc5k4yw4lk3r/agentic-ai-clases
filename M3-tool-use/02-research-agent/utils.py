"""Helpers del lab 02 (vienen dados; no hay lógica del ejercicio acá).

- hay_tavily(): True si TAVILY_API_KEY está configurada.
- mostrar_resultados(lista): imprime los resultados de una tool de búsqueda.
- comparar_schemas(mio, referencia): chequea la forma de un schema de tool escrito a mano.
- pipeline_completo(...): encadena investigar → reflexionar → HTML, cuenta llamadas y guarda el archivo.
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))


def hay_tavily() -> bool:
    """True si hay una TAVILY_API_KEY real en el entorno (no el placeholder del .env.example)."""
    key = os.getenv("TAVILY_API_KEY", "").strip()
    return bool(key) and not key.startswith("tvly-...")


def mostrar_resultados(resultados: list[dict], max_snippet: int = 160) -> None:
    """Imprime título, fecha/fuente, URL y un recorte del resumen de cada resultado."""
    if not resultados:
        print("(sin resultados)")
        return
    for i, r in enumerate(resultados, 1):
        extra = r.get("published") or r.get("source") or ""
        print(f"{i}. {r.get('title', '(sin título)')}  {extra}")
        print(f"   {r.get('url', '')}")
        snippet = r.get("snippet", "")
        if snippet:
            print(f"   {snippet[:max_snippet]}{'...' if len(snippet) > max_snippet else ''}")


def comparar_schemas(mio: dict, referencia: dict) -> bool:
    """Chequea que un schema de tool tenga la forma que espera la API y lo compara con la referencia.

    Imprime una línea por chequeo (OK / FALLA / AVISO) y devuelve True si no hubo fallas.
    Los avisos son diferencias con la referencia que no rompen nada (por ejemplo, exponer
    o no un parámetro opcional).
    """
    fallas = 0

    def ok(cond: bool, texto: str, aviso: bool = False) -> None:
        nonlocal fallas
        if cond:
            print(f"OK     {texto}")
        elif aviso:
            print(f"AVISO  {texto}")
        else:
            print(f"FALLA  {texto}")
            fallas += 1

    ok(mio.get("type") == "function", '"type" es "function"')
    fn = mio.get("function", {})
    ref_fn = referencia.get("function", {})
    ok(fn.get("name") == ref_fn.get("name"), f'"name" es "{ref_fn.get("name")}" (tiene que coincidir con la clave de tool_mapping)')
    ok(bool(fn.get("description", "").strip()), '"description" no está vacía')
    ok(len(fn.get("description", "")) >= 30, '"description" dice algo útil (30+ caracteres)', aviso=True)

    params = fn.get("parameters", {})
    ok(params.get("type") == "object", '"parameters.type" es "object"')
    props = params.get("properties", {})
    ok(isinstance(props, dict) and len(props) > 0, '"parameters.properties" tiene al menos un parámetro')
    ok(props.get("query", {}).get("type") == "string", '"query" existe y es string')
    ok(bool(props.get("query", {}).get("description", "").strip()), '"query" tiene descripción')
    ok("query" in params.get("required", []), '"query" está en "required"')

    ref_props = set(ref_fn.get("parameters", {}).get("properties", {}))
    mios = set(props)
    faltan = ref_props - mios
    sobran = mios - ref_props
    ok(not faltan, f"parámetros de la referencia que no expusiste: {sorted(faltan) or 'ninguno'}", aviso=True)
    ok(not sobran, f"parámetros que agregaste y la referencia no tiene: {sorted(sobran) or 'ninguno'}", aviso=True)

    print("Resultado:", "schema válido" if fallas == 0 else f"{fallas} falla(s) por corregir")
    return fallas == 0


def slug(texto: str, max_len: int = 60) -> str:
    """Convierte un título en un nombre de archivo seguro: minúsculas, sin acentos, guiones."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos).strip("-").lower()
    return limpio[:max_len] or "informe"


def pipeline_completo(tema: str, investigar, reflexionar, a_html, client, carpeta: str = "informes") -> dict:
    """Encadena las tres funciones del lab, cuenta las llamadas al modelo y guarda el HTML.

    Args:
        tema: qué investigar (se convierte en el pedido de investigar()).
        investigar: tu investigar_con_tools(pedido) -> str.
        reflexionar: tu reflexionar_y_reescribir(informe) -> dict.
        a_html: tu convertir_a_html(informe) -> str.
        client: el cliente de OpenAI del notebook (para contar llamadas).
        carpeta: dónde guardar el HTML.

    Returns:
        Dict con informe, critica, informe_revisado, html, llamadas (int) y archivo (ruta).
    """
    contador = {"n": 0}
    original = client.chat.completions.create

    def contar(*args, **kwargs):
        contador["n"] += 1
        return original(*args, **kwargs)

    client.chat.completions.create = contar
    try:
        pedido = (
            f"Escribí un informe breve (300 a 500 palabras) sobre: {tema}. "
            "Consultá al menos dos fuentes distintas y citá cada afirmación con su URL."
        )
        print("[1/3] investigando...")
        informe = investigar(pedido)
        print(f"[2/3] criticando y reescribiendo ({contador['n']} llamadas hasta acá)...")
        reflexion = reflexionar(informe)
        print(f"[3/3] convirtiendo a HTML ({contador['n']} llamadas hasta acá)...")
        html = a_html(reflexion["informe_revisado"])
    finally:
        client.chat.completions.create = original

    destino = Path(carpeta)
    destino.mkdir(exist_ok=True)
    archivo = destino / f"{slug(tema)}.html"
    archivo.write_text(html, encoding="utf-8")

    return {
        "informe": informe,
        "critica": reflexion["critica"],
        "informe_revisado": reflexion["informe_revisado"],
        "html": html,
        "llamadas": contador["n"],
        "archivo": str(archivo),
    }

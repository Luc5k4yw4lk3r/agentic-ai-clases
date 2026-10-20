"""Herramientas de investigación compartidas por M3, M4 y M5.

Tres tools que un agente puede llamar:

- ``arxiv_search_tool(query, max_results)``: papers académicos (API pública, sin key).
- ``wikipedia_search_tool(query, max_results)``: resúmenes de Wikipedia (API pública, sin key).
- ``tavily_search_tool(query, max_results)``: búsqueda web general. Necesita
  ``TAVILY_API_KEY``; si falta, cae a Wikipedia y lo avisa en el resultado.

Cada tool devuelve una **lista de dicts** con las mismas claves
(``title``, ``url``, ``snippet`` y, cuando aplica, ``published``/``authors``), para
que el agente las pueda comparar y citar.

Los docstrings están en español a propósito: ``aisuite`` los usa para armar el
schema de cada tool y el modelo los lee para decidir cuándo llamarla.

Al final del archivo están los schemas JSON escritos a mano
(``arxiv_tool_def``, ``tavily_tool_def``, ``wikipedia_tool_def``) para el lab que
hace function calling con el SDK de OpenAI, y ``tool_mapping`` para despachar.
"""
from __future__ import annotations

import os
import urllib.parse
import xml.etree.ElementTree as ET

import requests

USER_AGENT = "agentic-ai-clases/1.0 (material educativo)"
TIMEOUT = 20


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------
def arxiv_search_tool(query: str, max_results: int = 5) -> list[dict]:
    """Busca papers en arXiv y devuelve título, autores, fecha, resumen y URL.

    Args:
        query: tema a buscar, en inglés (arXiv indexa en inglés). Ej: "retrieval augmented generation".
        max_results: cantidad máxima de papers a devolver (1 a 20).

    Returns:
        Lista de dicts con las claves title, authors, published, snippet, url.
    """
    max_results = max(1, min(int(max_results), 20))
    # El original no codificaba la query: "retrieval-augmented generation" rompía la URL.
    url = (
        "https://export.arxiv.org/api/query?search_query="
        + urllib.parse.quote(f"all:{query}")
        + f"&start=0&max_results={max_results}"
    )
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return parse_arxiv_feed(resp.text)


def parse_arxiv_feed(xml_text: str) -> list[dict]:
    """Convierte el XML (Atom) que devuelve arXiv en una lista de dicts."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    papers = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
        link = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        authors = [
            (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
            for a in entry.findall("atom:author", ns)
        ]
        papers.append(
            {
                "title": " ".join(title.split()),
                "authors": authors,
                "published": published,
                "snippet": " ".join(summary.split())[:600],
                "url": link,
            }
        )
    return papers


# ---------------------------------------------------------------------------
# Wikipedia (API de MediaWiki, sin paquetes extra)
# ---------------------------------------------------------------------------
def wikipedia_search_tool(query: str, max_results: int = 3, lang: str = "en") -> list[dict]:
    """Busca artículos en Wikipedia y devuelve título, resumen y URL de cada uno.

    Args:
        query: tema a buscar. Ej: "transformer neural network".
        max_results: cantidad máxima de artículos (1 a 10).
        lang: idioma de la Wikipedia a consultar ("en" o "es").

    Returns:
        Lista de dicts con las claves title, snippet, url.
    """
    max_results = max(1, min(int(max_results), 10))
    api = f"https://{lang}.wikipedia.org/w/api.php"
    headers = {"User-Agent": USER_AGENT}

    # Paso 1: buscar títulos
    search = requests.get(
        api,
        params={"action": "query", "list": "search", "srsearch": query, "srlimit": max_results, "format": "json"},
        headers=headers,
        timeout=TIMEOUT,
    )
    search.raise_for_status()
    titles = [hit["title"] for hit in search.json().get("query", {}).get("search", [])]
    if not titles:
        return []

    # Paso 2: traer el resumen (primer párrafo) de cada título
    extracts = requests.get(
        api,
        params={
            "action": "query",
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
            "titles": "|".join(titles),
            "format": "json",
        },
        headers=headers,
        timeout=TIMEOUT,
    )
    extracts.raise_for_status()
    pages = extracts.json().get("query", {}).get("pages", {})
    results = []
    for page in pages.values():
        results.append(
            {
                "title": page.get("title", ""),
                "snippet": " ".join((page.get("extract") or "").split())[:600],
                "url": page.get("fullurl", ""),
            }
        )
    # mantener el orden de relevancia de la búsqueda
    orden = {t: i for i, t in enumerate(titles)}
    results.sort(key=lambda r: orden.get(r["title"], 99))
    return results


# ---------------------------------------------------------------------------
# Tavily (búsqueda web). Con fallback a Wikipedia si no hay key.
# ---------------------------------------------------------------------------
def tavily_search_tool(query: str, max_results: int = 5) -> list[dict]:
    """Busca en la web (noticias, blogs, documentación) y devuelve título, resumen y URL.

    Usala para información reciente o general que no está en arXiv ni en
    Wikipedia. Si no hay TAVILY_API_KEY configurada, busca en Wikipedia y lo
    indica en el campo "source".

    Args:
        query: lo que querés buscar, en inglés o español. Ej: "state of agentic AI 2026".
        max_results: cantidad máxima de resultados (1 a 10).

    Returns:
        Lista de dicts con las claves title, snippet, url, source.
    """
    max_results = max(1, min(int(max_results), 10))
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key or api_key.startswith("tvly-..."):
        fallback = wikipedia_search_tool(query, max_results=min(max_results, 5))
        for r in fallback:
            r["source"] = "wikipedia (fallback: falta TAVILY_API_KEY)"
        return fallback

    from tavily import TavilyClient  # import tardío: solo si hay key

    client = TavilyClient(api_key=api_key)
    kwargs = {"query": query, "max_results": max_results, "search_depth": "basic"}
    base_url = os.getenv("DLAI_TAVILY_BASE_URL")  # compatibilidad con el entorno del curso original
    if base_url:
        client.base_url = base_url
    data = client.search(**kwargs)
    return [
        {
            "title": r.get("title", ""),
            "snippet": " ".join((r.get("content") or "").split())[:600],
            "url": r.get("url", ""),
            "source": "tavily",
        }
        for r in data.get("results", [])
    ]


# ---------------------------------------------------------------------------
# Schemas a mano (para el SDK de OpenAI) y despacho
# ---------------------------------------------------------------------------
arxiv_tool_def = {
    "type": "function",
    "function": {
        "name": "arxiv_search_tool",
        "description": "Busca papers académicos en arXiv. Usar para fundamentos técnicos y trabajos de investigación.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tema a buscar, en inglés."},
                "max_results": {"type": "integer", "description": "Cantidad máxima de papers (1 a 20).", "default": 5},
            },
            "required": ["query"],
        },
    },
}

wikipedia_tool_def = {
    "type": "function",
    "function": {
        "name": "wikipedia_search_tool",
        "description": "Busca artículos en Wikipedia. Usar para definiciones y contexto general.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Tema a buscar."},
                "max_results": {"type": "integer", "description": "Cantidad máxima de artículos (1 a 10).", "default": 3},
            },
            "required": ["query"],
        },
    },
}

tavily_tool_def = {
    "type": "function",
    "function": {
        "name": "tavily_search_tool",
        "description": "Busca en la web (noticias, blogs, documentación). Usar para información reciente o general.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Lo que querés buscar."},
                "max_results": {"type": "integer", "description": "Cantidad máxima de resultados (1 a 10).", "default": 5},
            },
            "required": ["query"],
        },
    },
}

tool_mapping = {
    "arxiv_search_tool": arxiv_search_tool,
    "wikipedia_search_tool": wikipedia_search_tool,
    "tavily_search_tool": tavily_search_tool,
}

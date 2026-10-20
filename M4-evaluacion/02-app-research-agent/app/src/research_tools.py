"""Tools de investigación de la app: arXiv, Tavily y Wikipedia.

[Adaptación clase] Cambios respecto del original (agentic-ai-public/src/research_tools.py):

- Wikipedia: el original usaba el paquete ``wikipedia`` (abandonado, sin soporte en Python
  3.12+). Acá se consulta la API de MediaWiki con ``requests``, con la misma lógica que
  ``comun/research_tools.py`` del material.
- Tavily: si falta ``TAVILY_API_KEY`` cae a Wikipedia y lo avisa en el campo ``source`` (el
  original levantaba ``ValueError`` y el paso de research entero fallaba).
- arXiv: misma lógica (búsqueda + descarga del PDF para enriquecer el resumen), pero la
  descarga de PDFs se puede apagar con ``ARXIV_FETCH_PDF=0`` (más rápido en clase) y el
  archivo quedó con un solo bloque de imports (el original repetía los imports cinco veces).

Lo que NO cambió: los nombres y el comportamiento de las tres funciones, que devuelven
``[{"error": "..."}]`` en vez de levantar excepciones para que el agente pueda seguir.
"""
from __future__ import annotations

import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

USER_AGENT = "agentic-ai-clases/1.0 (material educativo)"
TIMEOUT = 30


# ----- Sesión HTTP con reintentos -----
def _build_session(user_agent: str = USER_AGENT) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent, "Accept": "*/*"})
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_redirect=False,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


session = _build_session()


# ===========================================================================
# arXiv
# ===========================================================================
def ensure_pdf_url(abs_or_pdf_url: str) -> str:
    url = abs_or_pdf_url.strip().replace("http://", "https://")
    if "/pdf/" in url and url.endswith(".pdf"):
        return url
    url = url.replace("/abs/", "/pdf/")
    if not url.endswith(".pdf"):
        url += ".pdf"
    return url


def clean_text(s: str) -> str:
    s = re.sub(r"-\n", "", s)  # "transfor-\nmers" -> "transformers"
    s = re.sub(r"\r\n|\r", "\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def fetch_pdf_bytes(pdf_url: str, timeout: int = 90) -> bytes:
    r = session.get(pdf_url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.content


def pdf_bytes_to_text(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
    # 1) PyMuPDF si está instalado (más rápido)
    try:
        import fitz  # PyMuPDF

        out = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            n = len(doc)
            limit = n if max_pages is None else min(max_pages, n)
            for i in range(limit):
                out.append(doc.load_page(i).get_text("text"))
        return "\n".join(out)
    except Exception:
        pass

    # 2) pdfminer.six
    try:
        from pdfminer.high_level import extract_text_to_fp

        buf_in = BytesIO(pdf_bytes)
        buf_out = BytesIO()
        extract_text_to_fp(buf_in, buf_out)
        return buf_out.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        raise RuntimeError(f"PDF text extraction failed: {e}")


def arxiv_search_tool(query: str, max_results: int = 3) -> List[Dict]:
    """Busca papers en arXiv. Devuelve título, autores, fecha, URL y resumen de cada uno.

    Si ARXIV_FETCH_PDF=1 (default), descarga el PDF y reemplaza el resumen por las primeras
    páginas del texto extraído.

    Args:
        query: tema a buscar, en inglés.
        max_results: cantidad máxima de papers (default 3).
    """
    fetch_pdf = os.getenv("ARXIV_FETCH_PDF", "1") == "1"
    max_pages = 6
    text_chars = 5000
    sleep_seconds = 1.0

    api_url = (
        "https://export.arxiv.org/api/query"
        f"?search_query=all:{urllib.parse.quote(query)}&start=0&max_results={int(max_results)}"
    )

    out: List[Dict] = []
    try:
        resp = session.get(api_url, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return [{"error": f"arXiv API request failed: {e}"}]

    try:
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
            url_abs = entry.findtext("atom:id", default="", namespaces=ns) or ""
            abstract_summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()

            authors = []
            for a in entry.findall("atom:author", ns):
                nm = a.findtext("atom:name", default="", namespaces=ns)
                if nm:
                    authors.append(nm)

            link_pdf = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    link_pdf = link.attrib.get("href")
                    break
            if not link_pdf and url_abs:
                link_pdf = ensure_pdf_url(url_abs)

            item = {
                "title": " ".join(title.split()),
                "authors": authors,
                "published": published,
                "url": url_abs,
                "summary": abstract_summary,
                "link_pdf": link_pdf,
            }

            if fetch_pdf and link_pdf:
                try:
                    pdf_bytes = fetch_pdf_bytes(link_pdf, timeout=90)
                    time.sleep(sleep_seconds)  # arXiv pide no más de una petición cada pocos segundos
                    text = clean_text(pdf_bytes_to_text(pdf_bytes, max_pages=max_pages))
                    if text:
                        item["summary"] = text[:text_chars]
                except Exception as e:
                    item["pdf_error"] = f"PDF fetch/extract failed: {e}"

            out.append(item)
        return out
    except ET.ParseError as e:
        return [{"error": f"arXiv API XML parse failed: {e}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {e}"}]


# ===========================================================================
# Wikipedia (API de MediaWiki con requests; misma lógica que comun/research_tools.py)
# ===========================================================================
def wikipedia_search_tool(query: str, max_results: int = 3, lang: str = "en") -> List[Dict]:
    """Busca artículos en Wikipedia y devuelve título, resumen y URL de cada uno.

    Args:
        query: tema a buscar. Ej: "transformer neural network".
        max_results: cantidad máxima de artículos (1 a 10).
        lang: idioma de la Wikipedia a consultar ("en" o "es").
    """
    try:
        max_results = max(1, min(int(max_results), 10))
        api = f"https://{lang}.wikipedia.org/w/api.php"

        # Paso 1: buscar títulos
        search = session.get(
            api,
            params={"action": "query", "list": "search", "srsearch": query, "srlimit": max_results, "format": "json"},
            timeout=TIMEOUT,
        )
        search.raise_for_status()
        titles = [hit["title"] for hit in search.json().get("query", {}).get("search", [])]
        if not titles:
            return []

        # Paso 2: traer el resumen (primer párrafo) de cada título
        extracts = session.get(
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
            timeout=TIMEOUT,
        )
        extracts.raise_for_status()
        pages = extracts.json().get("query", {}).get("pages", {})
        results = []
        for page in pages.values():
            results.append(
                {
                    "title": page.get("title", ""),
                    "summary": " ".join((page.get("extract") or "").split())[:600],
                    "url": page.get("fullurl", ""),
                }
            )
        orden = {t: i for i, t in enumerate(titles)}
        results.sort(key=lambda r: orden.get(r["title"], 99))
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ===========================================================================
# Tavily (búsqueda web). Con fallback a Wikipedia si no hay key.
# ===========================================================================
def tavily_search_tool(query: str, max_results: int = 5) -> List[Dict]:
    """Busca en la web (noticias, blogs, documentación) y devuelve título, resumen y URL.

    Si no hay TAVILY_API_KEY configurada, busca en Wikipedia y lo indica en el campo "source".

    Args:
        query: lo que querés buscar.
        max_results: cantidad máxima de resultados (1 a 10).
    """
    max_results = max(1, min(int(max_results), 10))
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key or api_key.startswith("tvly-..."):
        fallback = wikipedia_search_tool(query, max_results=min(max_results, 5))
        for r in fallback:
            r["source"] = "wikipedia (fallback: falta TAVILY_API_KEY)"
        return fallback

    try:
        from tavily import TavilyClient  # import tardío: solo si hay key

        client = TavilyClient(api_key=api_key)
        base_url = os.getenv("DLAI_TAVILY_BASE_URL")  # compatibilidad con el entorno del curso original
        if base_url:
            client.base_url = base_url
        data = client.search(query=query, max_results=max_results, search_depth="basic")
        return [
            {
                "title": r.get("title", ""),
                "content": " ".join((r.get("content") or "").split())[:600],
                "url": r.get("url", ""),
                "source": "tavily",
            }
            for r in data.get("results", [])
        ]
    except Exception as e:
        return [{"error": str(e)}]


# Tool mapping (para quien quiera despachar a mano con el SDK de OpenAI)
tool_mapping = {
    "tavily_search_tool": tavily_search_tool,
    "arxiv_search_tool": arxiv_search_tool,
    "wikipedia_search_tool": wikipedia_search_tool,
}

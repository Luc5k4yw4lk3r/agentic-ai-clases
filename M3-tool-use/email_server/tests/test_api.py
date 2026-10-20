"""Tests del servidor de email: un test por endpoint (los 10) más casos borde.

Correr desde `M3-tool-use/email_server/tests` (o desde cualquier lado):

    pytest -q

Usa `TestClient`, que levanta la app en memoria sin necesidad de uvicorn.
Cada test arranca con la casilla reiniciada (fixture `client`).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from email_server.main import app
from email_server.seed import MI_EMAIL

CLAVES = {"id", "remitente", "destinatario", "asunto", "cuerpo", "fecha", "leido"}


@pytest.fixture()
def client():
    """Cliente con la base reiniciada antes de cada test."""
    with TestClient(app) as c:  # el `with` dispara el lifespan (crea la tabla)
        r = c.get("/reset_database")
        assert r.status_code == 200
        yield c


# ---------------------------------------------------------------------------
# 1. GET /reset_database
# ---------------------------------------------------------------------------
def test_reset_database_vuelve_a_los_6_mails(client):
    client.delete("/emails/1")
    client.post("/send", json={"destinatario": "a@b.com", "asunto": "x", "cuerpo": "y"})
    r = client.get("/reset_database")
    assert r.status_code == 200
    assert r.json() == {"mensaje": "Base reiniciada", "cantidad": 6}
    ids = sorted(e["id"] for e in client.get("/emails").json())
    assert ids == [1, 2, 3, 4, 5, 6]


# ---------------------------------------------------------------------------
# 2. POST /send
# ---------------------------------------------------------------------------
def test_send_crea_el_mail_con_mi_remitente(client):
    payload = {"destinatario": "jefa@empresa.com", "asunto": "Reporte Q3", "cuerpo": "Va adjunto."}
    r = client.post("/send", json=payload)
    assert r.status_code == 201
    datos = r.json()
    assert set(datos) == CLAVES
    assert datos["remitente"] == MI_EMAIL
    assert datos["destinatario"] == "jefa@empresa.com"
    assert datos["leido"] is True
    assert datos["id"] == 7  # los 6 de la semilla ocupan 1..6


def test_send_rechaza_payload_incompleto(client):
    r = client.post("/send", json={"destinatario": "jefa@empresa.com"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 3. GET /emails
# ---------------------------------------------------------------------------
def test_list_emails_devuelve_todos_ordenados_del_mas_nuevo(client):
    r = client.get("/emails")
    assert r.status_code == 200
    emails = r.json()
    assert len(emails) == 6
    fechas = [e["fecha"] for e in emails]
    assert fechas == sorted(fechas, reverse=True)
    assert emails[0]["id"] == 6  # el review del PR es el más reciente


# ---------------------------------------------------------------------------
# 4. GET /emails/unread
# ---------------------------------------------------------------------------
def test_list_unread_solo_no_leidos(client):
    emails = client.get("/emails/unread").json()
    assert {e["id"] for e in emails} == {3, 4, 5, 6}
    assert all(e["leido"] is False for e in emails)


# ---------------------------------------------------------------------------
# 5. GET /emails/search
# ---------------------------------------------------------------------------
def test_search_busca_en_asunto_cuerpo_y_remitente_sin_mayusculas(client):
    por_asunto = client.get("/emails/search", params={"q": "REPORTE"}).json()
    assert {e["id"] for e in por_asunto} == {3}

    por_cuerpo = client.get("/emails/search", params={"q": "422"}).json()
    assert {e["id"] for e in por_cuerpo} == {4}

    por_remitente = client.get("/emails/search", params={"q": "rrhh@"}).json()
    assert {e["id"] for e in por_remitente} == {5}

    nada = client.get("/emails/search", params={"q": "zzzz-no-existe"}).json()
    assert nada == []


def test_search_sin_q_es_422(client):
    assert client.get("/emails/search").status_code == 422


# ---------------------------------------------------------------------------
# 6. GET /emails/filter
# ---------------------------------------------------------------------------
def test_filter_por_destinatario(client):
    mios = client.get("/emails/filter", params={"destinatario": MI_EMAIL}).json()
    assert {e["id"] for e in mios} == {1, 3, 4, 5, 6}
    a_jefa = client.get("/emails/filter", params={"destinatario": "JEFA@empresa.com"}).json()
    assert {e["id"] for e in a_jefa} == {2}


def test_filter_por_rango_de_fechas(client):
    hoy = date.today()
    ultimas_48h = client.get(
        "/emails/filter",
        params={"desde": (hoy - timedelta(days=1)).isoformat(), "hasta": hoy.isoformat()},
    ).json()
    # la semilla es relativa a "ahora": el after (hace 1 día) y el PR (hace 2 h)
    assert {e["id"] for e in ultimas_48h} == {5, 6}

    sin_filtros = client.get("/emails/filter").json()
    assert len(sin_filtros) == 6

    invertido = client.get("/emails/filter", params={"desde": "2030-01-01", "hasta": "2020-01-01"})
    assert invertido.status_code == 422


# ---------------------------------------------------------------------------
# 7. GET /emails/{id}
# ---------------------------------------------------------------------------
def test_get_email_por_id_y_404(client):
    r = client.get("/emails/3")
    assert r.status_code == 200
    assert r.json()["asunto"] == "Reporte trimestral"
    assert r.json()["remitente"] == "jefa@empresa.com"

    r404 = client.get("/emails/999")
    assert r404.status_code == 404
    assert "999" in r404.json()["detail"]


# ---------------------------------------------------------------------------
# 8. PATCH /emails/{id}/read
# ---------------------------------------------------------------------------
def test_mark_read(client):
    r = client.patch("/emails/3/read")
    assert r.status_code == 200
    assert r.json()["leido"] is True
    assert 3 not in {e["id"] for e in client.get("/emails/unread").json()}
    assert client.patch("/emails/999/read").status_code == 404


# ---------------------------------------------------------------------------
# 9. PATCH /emails/{id}/unread
# ---------------------------------------------------------------------------
def test_mark_unread(client):
    r = client.patch("/emails/1/unread")
    assert r.status_code == 200
    assert r.json()["leido"] is False
    assert 1 in {e["id"] for e in client.get("/emails/unread").json()}
    assert client.patch("/emails/999/unread").status_code == 404


# ---------------------------------------------------------------------------
# 10. DELETE /emails/{id}
# ---------------------------------------------------------------------------
def test_delete_email(client):
    r = client.delete("/emails/5")
    assert r.status_code == 200
    assert r.json() == {"mensaje": "Email borrado", "id": 5}
    assert client.get("/emails/5").status_code == 404
    assert len(client.get("/emails").json()) == 5
    assert client.delete("/emails/5").status_code == 404  # ya no está


# ---------------------------------------------------------------------------
# Flujo completo, como lo haría el agente del lab 01
# ---------------------------------------------------------------------------
def test_flujo_del_agente_leer_y_responder_a_la_jefa(client):
    no_leidos = client.get("/emails/unread").json()
    de_la_jefa = [e for e in no_leidos if e["remitente"] == "jefa@empresa.com"]
    assert len(de_la_jefa) == 1

    client.patch(f"/emails/{de_la_jefa[0]['id']}/read")
    enviado = client.post(
        "/send",
        json={"destinatario": "jefa@empresa.com", "asunto": "Re: Reporte trimestral", "cuerpo": "Lo mando el miércoles."},
    ).json()

    assert client.get(f"/emails/{enviado['id']}").json()["destinatario"] == "jefa@empresa.com"
    assert "jefa@empresa.com" not in {e["remitente"] for e in client.get("/emails/unread").json()}

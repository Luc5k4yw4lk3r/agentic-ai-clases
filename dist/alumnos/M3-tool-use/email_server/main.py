"""Servidor de email simulado (FastAPI + SQLAlchemy + SQLite).

Diez endpoints, los mismos que listaba el material original del curso:

| Método | Ruta                        | Qué hace                                   |
|--------|-----------------------------|--------------------------------------------|
| GET    | /reset_database             | Vuelve a cargar los 6 mails semilla        |
| POST   | /send                       | "Envía" un mail (lo guarda en la casilla)  |
| GET    | /emails                     | Lista todos, del más nuevo al más viejo    |
| GET    | /emails/unread              | Lista solo los no leídos                   |
| GET    | /emails/search?q=...        | Busca texto en asunto, cuerpo o remitente  |
| GET    | /emails/filter              | Filtra por destinatario y/o rango de fechas|
| GET    | /emails/{email_id}          | Trae un mail por id                        |
| PATCH  | /emails/{email_id}/read     | Marca como leído                           |
| PATCH  | /emails/{email_id}/unread   | Marca como no leído                        |
| DELETE | /emails/{email_id}          | Borra un mail                              |

Levantarlo desde `M3-tool-use/`:

    uvicorn email_server.main:app --reload --port 8000

Y probarlo en http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, SessionLocal, engine, get_db
from .seed import MI_EMAIL, cargar_semilla


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Al arrancar: crea la tabla si no existe y carga la semilla si está vacía."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Email).count() == 0:
            cargar_semilla(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Servidor de email simulado (M3 · Tool use)",
    description="Una casilla de mentira para que un agente practique sin mandar mails reales.",
    version="1.0",
    lifespan=lifespan,
)


def _buscar_o_404(db: Session, email_id: int) -> models.Email:
    """Trae el mail o corta con 404 (mensaje en español para que el agente lo entienda)."""
    email = db.get(models.Email, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail=f"No existe un email con id {email_id}")
    return email


def _ordenados(consulta):
    """Del más nuevo al más viejo (y por id para desempatar)."""
    return consulta.order_by(models.Email.fecha.desc(), models.Email.id.desc())


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
@app.get("/reset_database", response_model=schemas.ResetOut, tags=["utilidades"])
def reset_database(db: Session = Depends(get_db)):
    """Borra todo y vuelve a cargar los 6 mails semilla. Útil entre corridas del agente."""
    cantidad = cargar_semilla(db)
    return {"mensaje": "Base reiniciada", "cantidad": cantidad}


# ---------------------------------------------------------------------------
# Enviar
# ---------------------------------------------------------------------------
@app.post("/send", response_model=schemas.EmailOut, status_code=201, tags=["emails"])
def send_email(datos: schemas.EmailNuevo, db: Session = Depends(get_db)):
    """Guarda un mail saliente. El remitente siempre es tu dirección (vos@empresa.com)."""
    email = models.Email(
        remitente=MI_EMAIL,
        destinatario=datos.destinatario,
        asunto=datos.asunto,
        cuerpo=datos.cuerpo,
        fecha=datetime.now(),
        leido=True,  # lo escribiste vos: no tiene sentido que figure como "no leído"
    )
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


# ---------------------------------------------------------------------------
# Listar / buscar / filtrar
# OJO con el orden: estas rutas van ANTES de /emails/{email_id}. Si no, FastAPI
# intentaría interpretar "unread" o "search" como un email_id y devolvería 422.
# ---------------------------------------------------------------------------
@app.get("/emails", response_model=list[schemas.EmailOut], tags=["emails"])
def list_emails(db: Session = Depends(get_db)):
    """Todos los mails, del más nuevo al más viejo."""
    return _ordenados(db.query(models.Email)).all()


@app.get("/emails/unread", response_model=list[schemas.EmailOut], tags=["emails"])
def list_unread(db: Session = Depends(get_db)):
    """Solo los no leídos."""
    return _ordenados(db.query(models.Email).filter(models.Email.leido.is_(False))).all()


@app.get("/emails/search", response_model=list[schemas.EmailOut], tags=["emails"])
def search_emails(q: str = Query(..., min_length=1, description="Texto a buscar"), db: Session = Depends(get_db)):
    """Busca `q` (sin distinguir mayúsculas) en el asunto, el cuerpo o el remitente."""
    patron = f"%{q.lower()}%"
    consulta = db.query(models.Email).filter(
        or_(
            func.lower(models.Email.asunto).like(patron),
            func.lower(models.Email.cuerpo).like(patron),
            func.lower(models.Email.remitente).like(patron),
        )
    )
    return _ordenados(consulta).all()


@app.get("/emails/filter", response_model=list[schemas.EmailOut], tags=["emails"])
def filter_emails(
    destinatario: str | None = Query(None, description="Dirección exacta del destinatario"),
    desde: date | None = Query(None, description="Fecha inicial, YYYY-MM-DD (inclusive)"),
    hasta: date | None = Query(None, description="Fecha final, YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
):
    """Filtra por destinatario y/o rango de fechas. Todos los filtros son opcionales y se combinan."""
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=422, detail="'desde' no puede ser posterior a 'hasta'")
    consulta = db.query(models.Email)
    if destinatario:
        consulta = consulta.filter(func.lower(models.Email.destinatario) == destinatario.lower())
    if desde:
        consulta = consulta.filter(models.Email.fecha >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        # inclusive: todo lo que pasó antes de que empiece el día siguiente
        fin = datetime.combine(hasta, datetime.min.time()) + timedelta(days=1)
        consulta = consulta.filter(models.Email.fecha < fin)
    return _ordenados(consulta).all()


# ---------------------------------------------------------------------------
# Un mail en particular
# ---------------------------------------------------------------------------
@app.get("/emails/{email_id}", response_model=schemas.EmailOut, tags=["emails"])
def get_email(email_id: int, db: Session = Depends(get_db)):
    """Trae un mail por id. 404 si no existe."""
    return _buscar_o_404(db, email_id)


@app.patch("/emails/{email_id}/read", response_model=schemas.EmailOut, tags=["emails"])
def mark_read(email_id: int, db: Session = Depends(get_db)):
    """Marca el mail como leído y lo devuelve actualizado."""
    email = _buscar_o_404(db, email_id)
    email.leido = True
    db.commit()
    db.refresh(email)
    return email


@app.patch("/emails/{email_id}/unread", response_model=schemas.EmailOut, tags=["emails"])
def mark_unread(email_id: int, db: Session = Depends(get_db)):
    """Marca el mail como no leído y lo devuelve actualizado."""
    email = _buscar_o_404(db, email_id)
    email.leido = False
    db.commit()
    db.refresh(email)
    return email


@app.delete("/emails/{email_id}", response_model=schemas.Mensaje, tags=["emails"])
def delete_email(email_id: int, db: Session = Depends(get_db)):
    """Borra el mail. 404 si no existe."""
    email = _buscar_o_404(db, email_id)
    db.delete(email)
    db.commit()
    return {"mensaje": "Email borrado", "id": email_id}

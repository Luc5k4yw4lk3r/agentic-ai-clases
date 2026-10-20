# Servidor de email simulado

Una casilla de correo de mentira, servida por una API REST, para que el agente
del lab 01 practique sin mandar mails reales. El material original del curso
usaba este servidor pero no incluía su código; esta es una reconstrucción a
partir de la lista de endpoints del README original.

## Lo que ya conocés

Es **el mismo patrón que TaskFlow**, el proyecto FastAPI que armaron en el
módulo anterior:

| En TaskFlow            | Acá                      | Para qué sirve                                   |
|------------------------|--------------------------|--------------------------------------------------|
| `database.py`          | `database.py`            | engine + `SessionLocal` + dependencia `get_db()` |
| `models.py` (`Tarea`)  | `models.py` (`Email`)    | la tabla, con SQLAlchemy                         |
| `schemas.py`           | `schemas.py`             | qué entra y qué sale por HTTP, con Pydantic      |
| `main.py` con routers  | `main.py` (todo junto)   | los endpoints                                    |
| `POST /tareas`         | `POST /send`             | crear                                            |
| `PATCH /tareas/{id}`   | `PATCH /emails/{id}/read`| modificar un campo                               |
| `DELETE /tareas/{id}`  | `DELETE /emails/{id}`    | borrar                                           |

La diferencia es quién llama a la API: en TaskFlow era el frontend (JavaScript
con `fetch`); acá va a ser **un LLM**, a través de funciones Python que envuelven
cada endpoint (las "tools"). La API no se entera de la diferencia.

Lo único nuevo es `seed.py`: carga 6 mails de ejemplo en español, con fechas
relativas al momento del arranque. Tu dirección es siempre `vos@empresa.com`.

## Levantarlo

Desde la carpeta `M3-tool-use/` (no desde `email_server/`):

```bash
uvicorn email_server.main:app --reload --port 8000
```

Dejá esa terminal abierta. La primera vez crea `email_server/emails.db` y la
carga con la semilla. Si en algún momento querés volver al estado inicial:

```bash
curl http://localhost:8000/reset_database
```

o abrí esa URL en el navegador.

## Probarlo con /docs

Abrí <http://localhost:8000/docs>. Es la documentación interactiva de FastAPI
(Swagger): cada endpoint tiene un botón **Try it out** que te deja mandarle
parámetros y ver la respuesta. Antes de pasarle los controles al agente,
probá a mano:

1. `GET /emails` → tenés que ver 6 mails.
2. `GET /emails/unread` → 4 (el newsletter y el que mandaste vos ya están leídos).
3. `GET /emails/search?q=reporte` → el de la jefa.
4. `POST /send` con `{"destinatario": "jefa@empresa.com", "asunto": "Hola", "cuerpo": "Prueba"}` → status 201 y el mail creado con `id` 7.
5. `DELETE /emails/7` → `{"mensaje": "Email borrado", "id": 7}`.

## Los 10 endpoints

| Método | Ruta                        | Qué hace                                      |
|--------|-----------------------------|-----------------------------------------------|
| GET    | `/reset_database`           | Vuelve a cargar los 6 mails semilla           |
| POST   | `/send`                     | Guarda un mail saliente (remitente: vos)      |
| GET    | `/emails`                   | Lista todos, del más nuevo al más viejo       |
| GET    | `/emails/unread`            | Solo los no leídos                            |
| GET    | `/emails/search?q=...`      | Busca texto en asunto, cuerpo o remitente     |
| GET    | `/emails/filter`            | Por `destinatario`, `desde`, `hasta` (opcionales) |
| GET    | `/emails/{id}`              | Un mail por id (404 si no existe)             |
| PATCH  | `/emails/{id}/read`         | Marca como leído                              |
| PATCH  | `/emails/{id}/unread`       | Marca como no leído                           |
| DELETE | `/emails/{id}`              | Borra                                         |

Un mail se ve así en todas las respuestas:

```json
{
  "id": 3,
  "remitente": "jefa@empresa.com",
  "destinatario": "vos@empresa.com",
  "asunto": "Reporte trimestral",
  "cuerpo": "Hola, ¿me pasás el reporte del Q3 antes del jueves? ...",
  "fecha": "2026-10-15T10:12:33.120000",
  "leido": false
}
```

## Un detalle que vale la pena mirar en `main.py`

Las rutas `/emails/unread`, `/emails/search` y `/emails/filter` están declaradas
**antes** que `/emails/{email_id}`. Si estuvieran después, FastAPI trataría de
convertir `"unread"` a `int` para `email_id` y devolvería 422. El orden de los
decoradores importa; es un error clásico que seguramente alguno ya sufrió en
TaskFlow.

## Tests

```bash
cd M3-tool-use/email_server/tests
pytest -q
```

Catorce tests con `TestClient`: uno por endpoint, casos de 404/422 y un flujo
completo (buscar no leídos de la jefa, marcarlos, responder). Usan una base
temporal, así que no tocan la casilla con la que trabaja el notebook.

## Variables de entorno

- `M3_EMAIL_SERVER_API_URL` (en el `.env` de la raíz): la URL que usan las
  tools del lab 01. Por defecto `http://localhost:8000`.
- `M3_EMAIL_DB_PATH` (opcional): ruta del archivo SQLite. Los tests la apuntan a
  un temporal; en clase no hace falta tocarla.

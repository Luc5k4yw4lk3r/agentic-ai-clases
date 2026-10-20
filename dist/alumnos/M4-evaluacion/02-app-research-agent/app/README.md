# Reflective Research Agent (FastAPI) — copia adaptada para clase

App web que planifica un flujo de investigación, ejecuta agentes con tools (Tavily, arXiv,
Wikipedia) y guarda el estado de cada tarea en una base de datos. Es el código de
[agentic-ai-public](https://github.com/https-deeplearning-ai/agentic-ai-public) de
DeepLearning.AI con cambios mínimos para que corra en el entorno del bootcamp (lista completa
al final).

La guía de lectura y los ejercicios están un nivel arriba, en `../guia_lectura.md` y
`../ejercicios.md`. Este README solo explica cómo correrla.

## Qué hace

| Endpoint | Qué devuelve |
|---|---|
| `GET /` | La UI (una página con un textarea y polling cada 2 s). |
| `POST /generate_report` | `{"task_id": "..."}`. Llama al planner (síncrono, 10-30 s) y lanza el workflow en un thread. |
| `GET /task_progress/{task_id}` | Estado de cada paso del plan (en memoria). |
| `GET /task_status/{task_id}` | Estado final + reporte (desde la base de datos). |
| `GET /api` | `{"status": "ok"}` (health check). |
| `GET /docs` | Swagger generado por FastAPI. |

## Opción A: correrla sin Docker (recomendada para la clase)

Necesitás Python 3.11+ y las dependencias del material ya instaladas (`requirements.txt` de la
raíz las cubre, salvo `pdfminer.six` y `psycopg2-binary`, que solo hacen falta si querés PDFs
de arXiv o Postgres).

```bash
cd M4-evaluacion/02-app-research-agent/app
cp .env.example .env            # completá OPENAI_API_KEY (y TAVILY_API_KEY si tenés)
pip install -r requirements.txt # opcional si ya instalaste el requirements de la raíz
uvicorn main:app --reload --port 8000
```

Abrí <http://localhost:8000>. Con `DATABASE_URL=sqlite:///./tasks.db` (el valor del
`.env.example`) la base es un archivo `tasks.db` en esta carpeta; no hace falta Postgres.

Para que el paso de research sea más rápido en clase, agregá `ARXIV_FETCH_PDF=0` al `.env`
(no descarga los PDFs de arXiv, solo usa el abstract).

## Opción B: Docker (Postgres + API en un contenedor)

El contenedor arranca un Postgres interno, crea usuario y base, y lanza uvicorn. **Solo se
publica el puerto 8000**: Postgres queda adentro del contenedor, nadie de la red del aula
puede conectarse a él. (El README original publicaba también el 5432 con usuario `app` y
clave `local`; no lo hagas.)

```bash
cd M4-evaluacion/02-app-research-agent/app
cp .env.example .env            # completá las keys; dejá DATABASE_URL comentada o borrala:
                                # el entrypoint define la URL interna de Postgres
docker build -t research-agent .
docker run --rm -it -p 8000:8000 --name research-agent --env-file .env research-agent
```

Si en tu `.env` quedó `DATABASE_URL=sqlite:///./tasks.db`, el contenedor va a usar sqlite y a
ignorar el Postgres que arrancó. Funciona igual; es solo redundante.

Para entrar a la base desde adentro del contenedor:

```bash
docker exec -it research-agent psql "postgresql://app:local@127.0.0.1:5432/appdb" -c "select id, status, created_at from tasks;"
```

## Variables de entorno

| Variable | Obligatoria | Qué hace |
|---|---|---|
| `OPENAI_API_KEY` | sí | Clave de OpenAI. |
| `DATABASE_URL` | sí (sin Docker) | `sqlite:///./tasks.db` o `postgresql://user:pass@host:5432/db`. Si falta, la app frena con un mensaje que lo explica. |
| `MODEL_CHEAP` | no (default `gpt-4.1-mini`) | Research, writer, editor. |
| `MODEL_STRONG` | no (default `gpt-4.1`) | Planner. |
| `TAVILY_API_KEY` | no | Búsqueda web. Si falta, la tool usa Wikipedia y lo avisa en el campo `source`. |
| `RESET_DB` | no | `1` borra las tablas al arrancar. El original lo hacía siempre. |
| `ARXIV_FETCH_PDF` | no (default `1`) | `0` desactiva la descarga de PDFs de arXiv. |

## Probarla desde la terminal

```bash
curl -X POST http://localhost:8000/generate_report \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Retrieval-augmented generation: estado del arte 2025, enfoque en evaluación"}'
# -> {"task_id":"..."}
curl http://localhost:8000/task_progress/<TASK_ID>
curl http://localhost:8000/task_status/<TASK_ID>
```

Una corrida completa son 6 a 7 pasos y entre 8 y 12 llamadas al modelo (más las tools). Tarda
de 2 a 6 minutos según el tema y si se descargan PDFs.

## Troubleshooting

| Síntoma | Causa | Arreglo |
|---|---|---|
| `RuntimeError: Falta la variable de entorno DATABASE_URL` | No hay `.env` o no tiene `DATABASE_URL` | `cp .env.example .env` |
| La UI muestra el spinner "Generating steps" durante 30 s sin nada más | Es normal: el planner es síncrono y el `POST` no responde hasta que termina | Esperar. Ejercicio de diseño en `../ejercicios.md` |
| El primer paso dice `wikipedia (fallback: falta TAVILY_API_KEY)` | No hay key de Tavily | Es el comportamiento esperado sin key; agregá la key si querés búsqueda web real |
| `ModuleNotFoundError: psycopg2` | Usaste `postgresql://` sin instalar el driver | `pip install psycopg2-binary` o usá sqlite |
| El paso de research tarda más de 2 minutos | Está descargando PDFs de arXiv | `ARXIV_FETCH_PDF=0` en el `.env` |
| Reiniciás la app y las tareas desaparecen | `RESET_DB=1` en el `.env` | Sacalo |
| Las tareas viejas devuelven `{"steps": []}` en `/task_progress` | El progreso vive en memoria (`task_progress = {}`); se pierde al reiniciar. El resultado final sí está en la DB | Es un bug de diseño; ver `../ejercicios.md` |

## Qué cambió respecto del original

Cambios mínimos para que corra, todos marcados con `# [Adaptación clase]` en el código:

1. **Modelos desde `.env`** (`src/config.py`): `MODEL_CHEAP` para research/writer/editor,
   `MODEL_STRONG` para el planner. El original tenía `openai:o4-mini` y `openai:gpt-4.1-mini`
   escritos en cada función (y `o4-mini` está retirado).
2. **Error claro si falta `DATABASE_URL`** (`main.py`). El original hacía
   `DATABASE_URL.startswith("postgres://")` antes de chequear si era `None`, así que fallaba
   con `AttributeError: 'NoneType' object has no attribute 'startswith'`.
3. **`drop_all` solo con `RESET_DB=1`** (`main.py`). El original borraba las tablas en cada
   arranque.
4. **Soporte sqlite** (`main.py`): `check_same_thread=False` cuando la URL empieza con `sqlite`,
   porque el workflow corre en otro thread.
5. **`TemplateResponse(request, "index.html", {})`** (`main.py`): el orden viejo de argumentos
   falla con Starlette actual (`unhashable type: 'dict'`).
6. **Wikipedia con `requests`** (`src/research_tools.py`) en lugar del paquete `wikipedia`
   (abandonado). **Tavily con fallback** a Wikipedia si falta la key (el original levantaba
   `ValueError` y el paso entero fallaba). Un solo bloque de imports (el original repetía
   los imports cinco veces). `ARXIV_FETCH_PDF` para apagar la descarga de PDFs.
7. **`requirements.txt` con versiones** compatibles con `aisuite>=0.2` y sin duplicados.
8. **Dockerfile y entrypoint**: solo `EXPOSE 8000`; texto sin emojis.
9. **`templates/index.html`**: el párrafo que decía "powered by GPT-4.1-mini and o4-mini"
   ahora dice que los modelos salen del `.env`. La lógica JS de polling no se tocó.
10. **No se copiaron los logos** de `static/` (imágenes con marca). La carpeta existe vacía
    porque `main.py` la monta.

Lo que **no** se cambió a propósito: el ruteo por palabras clave de `executor_agent_step`, la
forma en que se guarda y se lee el historial, los parámetros sin usar de `writer_agent`, el
`task_progress` en memoria, el CORS abierto y el planner síncrono. Son el material de la caza
de bugs y de los ejercicios (`../ejercicios.md`).

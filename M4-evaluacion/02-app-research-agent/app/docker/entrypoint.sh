#!/usr/bin/env bash
set -euo pipefail

# --- Arranca el cluster de Postgres que trae Debian ---
PG_MAJOR="$(psql -V | awk '{print $3}' | cut -d. -f1)"
echo "Arrancando Postgres ${PG_MAJOR}/main..."
pg_ctlcluster "${PG_MAJOR}" main start

# Espera a que acepte conexiones
for i in $(seq 1 60); do
  if pg_isready -h 127.0.0.1 -p 5432 -U postgres >/dev/null 2>&1; then
    echo "Postgres listo"
    break
  fi
  sleep 1
done

# --- Usuario / base de datos de la app ---
: "${POSTGRES_USER:=app}"
: "${POSTGRES_PASSWORD:=local}"
: "${POSTGRES_DB:=appdb}"

# Crea el rol si no existe (peer auth por socket UNIX: no pide clave)
if ! su -s /bin/bash postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_USER}'\"" | grep -q 1; then
  su -s /bin/bash postgres -c "psql -c \"CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';\""
fi

# Crea la base si no existe
if ! su -s /bin/bash postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'\"" | grep -q 1; then
  su -s /bin/bash postgres -c "psql -c \"CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};\""
fi

# DATABASE_URL para la app (solo dentro del contenedor: 127.0.0.1)
export DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}}"
echo "DATABASE_URL=${DATABASE_URL}"

# Lanza FastAPI
exec uvicorn main:app --host 0.0.0.0 --port 8000

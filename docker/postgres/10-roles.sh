#!/bin/sh
# Runs once on an empty data directory. POSTGRES_USER owns the schema (migrations);
# the application role gets DML only via grants in the migration and cannot bypass RLS (ADR-0002).
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_DB_USER};
SQL

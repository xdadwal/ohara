#!/usr/bin/env bash
# Official Postgres entrypoint sources this only for a new, empty cluster.
# Never execute dotenv. Read a validated literal secret and quote SQL apostrophes.
set -euo pipefail
kutt_db_password="$(cat /run/secrets/db_password)"
kutt_sql_password="${kutt_db_password//\'/\'\'}"
psql --username postgres --dbname postgres --set ON_ERROR_STOP=1 <<SQL
CREATE ROLE kutt WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '$kutt_sql_password';
CREATE DATABASE kutt OWNER kutt;
ALTER ROLE postgres PASSWORD NULL;
SQL
unset kutt_db_password kutt_sql_password
touch /var/lib/postgresql/data/.ohara-kutt-initialized

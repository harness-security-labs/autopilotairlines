#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE cardservice;
    GRANT ALL PRIVILEGES ON DATABASE cardservice TO autopilot;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "cardservice" -f /docker-entrypoint-initdb.d/03-cardservice-init.sql

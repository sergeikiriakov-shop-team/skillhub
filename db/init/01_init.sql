-- Runs once on first container start (docker-entrypoint-initdb.d).
-- Enables pgvector in the main database and provisions a separate DB for Airflow.

CREATE EXTENSION IF NOT EXISTS vector;

-- Airflow metadata DB. Created only if missing.
SELECT 'CREATE DATABASE airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec

-- pgvector is not required inside the airflow DB, so nothing else to do here.

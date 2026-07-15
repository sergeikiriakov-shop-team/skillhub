-- Runs once on first container start (docker-entrypoint-initdb.d).
-- Enables pgvector in the main database.

CREATE EXTENSION IF NOT EXISTS vector;

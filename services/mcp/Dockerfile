# Build context = services/mcp. Small image (no torch): mcp + httpx only.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY server.py /app/server.py

# stdio MCP server — Claude Code spawns it with `docker run -i`.
ENTRYPOINT ["python", "/app/server.py"]

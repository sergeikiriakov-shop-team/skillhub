FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System libs needed by torch (pulled in by sentence-transformers).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Install CPU-only PyTorch first. sentence-transformers pulls torch, and the default Linux
# wheel is the huge CUDA build (~2GB of nvidia deps). The CPU wheel is a fraction of the size
# — critical on slow / VPN networks. skillhub_core then finds torch already satisfied.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

# Install the shared core (brings SQLAlchemy, pgvector, langchain, sentence-transformers, ...).
COPY packages/skillhub_core /tmp/skillhub_core
RUN pip install /tmp/skillhub_core

# API-specific dependencies.
COPY services/api/requirements.txt /tmp/api-requirements.txt
RUN pip install -r /tmp/api-requirements.txt

# Application code (also bind-mounted in dev for hot reload).
COPY services/api/app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

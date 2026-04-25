
FROM python:3.12-slim AS builder

# uv viene como binario estático desde su imagen oficial
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev


FROM python:3.12-slim

WORKDIR /app

# Trae el venv ya sincronizado del builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copiamos solo el código que el servidor necesita
COPY app/ ./app/
COPY config.py main.py ./

# Usuario no-root (recomendación de seguridad estándar)
RUN useradd --create-home --uid 1000 biosim && chown -R biosim:biosim /app
USER biosim

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

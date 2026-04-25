# =============================================================================
# Stage 1 — builder: instala dependencias con uv en un .venv aislado
# =============================================================================
FROM python:3.12-slim AS builder

# uv viene como binario estático desde su imagen oficial
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

WORKDIR /app

# Copiamos solo los manifiestos para aprovechar la caché de Docker:
# si no cambian, no se reinstalan las dependencias.
COPY pyproject.toml uv.lock ./

# `--frozen --no-dev` instala exactamente lo que dice el lockfile, sin tooling
# de desarrollo (ruff, pytest, pre-commit).
RUN uv sync --frozen --no-dev


# =============================================================================
# Stage 2 — runtime: imagen mínima con el venv pre-construido y el código
# =============================================================================
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

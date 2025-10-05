# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

ENV PORT=8000

EXPOSE 8000

CMD [ \
    "uvicorn", \
    "textadventure.api.app:create_app", \
    "--factory", \
    "--host", "0.0.0.0", \
    "--port", "8000" \
]

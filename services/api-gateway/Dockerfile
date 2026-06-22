FROM python:3.12-slim AS base

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    UV_HTTP_TIMEOUT=300

WORKDIR /app

RUN pip install --no-cache-dir --timeout 300 --retries 10 uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

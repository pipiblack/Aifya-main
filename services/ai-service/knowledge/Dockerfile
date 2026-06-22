FROM python:3.12-slim

ENV PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10

WORKDIR /app

# System deps for PyMuPDF and document parsing
RUN apt-get -o Acquire::Retries=5 update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 10 -r requirements.txt

COPY . .

EXPOSE 8025

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8025", "--workers", "2"]

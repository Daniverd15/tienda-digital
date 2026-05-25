FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN pip install fastapi==0.115.0 uvicorn[standard]==0.32.0 pydantic==2.9.2

COPY app ./app

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 9000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]

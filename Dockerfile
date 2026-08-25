FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY cloud/requirements.txt /app/cloud/requirements.txt
RUN pip install --no-cache-dir -r /app/cloud/requirements.txt

COPY cloud /app/cloud
COPY gallery /app/gallery

CMD ["sh", "-c", "alembic -c cloud/alembic.ini upgrade head && exec uvicorn cloud.app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]

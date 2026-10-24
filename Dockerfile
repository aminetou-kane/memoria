# Image de déploiement de Mémoria (API + interface web servies par une seule application)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend backend
COPY db db

WORKDIR /app/backend
EXPOSE 8000
# Les hébergeurs (Render, Railway...) fournissent le port dans la variable PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

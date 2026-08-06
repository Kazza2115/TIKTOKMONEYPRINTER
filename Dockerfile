FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# Sur un petit serveur cloud : modèle Whisper léger et données en /tmp
ENV DATA_DIR=/tmp/data \
    WHISPER_MODEL=tiny \
    WHISPER_DEVICE=cpu \
    PYTHONUNBUFFERED=1

EXPOSE 7860

# 1 worker + threads : les jobs tournent en threads d'arrière-plan,
# l'état en mémoire doit rester dans un seul process
CMD gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:${PORT:-7860} "app:create_app()"

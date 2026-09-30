FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt
COPY server.py core.py keywords.py fusion_import.py cloud_transcription.py roman_urdu.py cloud_store.py fonts.py ./
COPY static ./static

ENV PYTHONUNBUFFERED=1 CAPTION_DATA=/tmp/ahsan-caption-data
EXPOSE 10000
CMD ["python", "server.py"]

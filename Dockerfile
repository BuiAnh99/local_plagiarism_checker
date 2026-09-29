FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAGIARISM_STORE=/app/data \
    EMBEDDING_MODEL_PATH=/app/models/vietnamese-sbert \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-vie \
      libreoffice-writer \
      poppler-utils \
      fonts-dejavu \
      fonts-liberation \
      fonts-noto-core \
      fonts-noto-cjk \
      fonts-noto-color-emoji && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-semantic.txt ./
ARG INSTALL_SEMANTIC=false
RUN pip install --no-cache-dir --upgrade pip && \
    if [ "$INSTALL_SEMANTIC" = "true" ]; then \
      pip install --no-cache-dir -r requirements-semantic.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .
EXPOSE 8000
VOLUME ["/app/data", "/app/corpus", "/app/models"]
CMD ["python", "cli.py", "serve", "--host", "0.0.0.0", "--port", "8000"]

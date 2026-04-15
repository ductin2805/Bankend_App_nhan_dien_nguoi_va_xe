FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# Install CPU-only PyTorch to save ~1GB
RUN pip install --upgrade pip && \
    pip install --index-url https://download.pytorch.org/whl/cpu torch==2.2.1 torchvision==0.17.1 && \
    pip install -r requirements.txt

# Remove build dependencies to save space (~500MB)
RUN apt-get remove -y build-essential g++ && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p runs

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
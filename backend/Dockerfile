# backend/Dockerfile
FROM python:3.12-slim

# 🔧 Системные зависимости для llama-cpp-python
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 📦 Рабочая директория
WORKDIR /app

# 📋 Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 📁 Копируем код приложения
COPY app/ ./app/

# 🔍 Health check для FastAPI
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 🚀 Порт
EXPOSE 8000

# ▶️ Запуск
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
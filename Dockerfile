FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY neural_analyzer.py .
COPY datasets/ ./datasets/

RUN mkdir -p /app/models

CMD ["python", "neural_analyzer.py"]
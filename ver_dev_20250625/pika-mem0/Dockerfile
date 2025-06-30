FROM python:3.10-slim

WORKDIR /app

RUN apt update && apt install -y curl build-essential && \
    curl https://sh.rustup.rs -sSf | sh -s -- -y && \
    apt clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY modules/OpenAITriton /app/modules/OpenAITriton
RUN pip install -e modules/OpenAITriton

COPY modules/mem0 /app/modules/mem0
RUN pip install -e modules/mem0

COPY .env /app/.env
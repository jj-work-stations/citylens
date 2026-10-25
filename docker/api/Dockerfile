# docker/api/Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip config --user set global.index https://package-mirror.liara.ir/repository/pypi/simple
RUN pip config --user set global.index-url https://package-mirror.liara.ir/repository/pypi/simple
RUN pip config --user set global.trusted-host package-mirror.liara.ir
RUN pip config --user set global.timeout 60


RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001
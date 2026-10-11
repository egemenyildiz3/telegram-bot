FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/codex \
    CODEX_HOME=/home/codex/.codex

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git nodejs npm \
    && npm install --global @openai/codex@0.161.0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.npm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY telegram_bot.py .

RUN mkdir -p /home/codex/.codex
ENTRYPOINT ["python", "-u", "telegram_bot.py"]

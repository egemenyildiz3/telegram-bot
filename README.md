# Telegram Bot for my Homelab

## Docker

```bash
cd /home/egemen/homelab/TelegramBot
docker compose up -d --build
docker compose logs -f telegram-codex
```

Yeniden başlatmak veya durdurmak için:

```bash
docker compose restart
docker compose down
```

Container root olarak çalışmaz. Homelab `/workspace` olarak bağlanır; Codex ayarları salt-okunur bağlanır.

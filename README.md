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

Container root olarak çalışmaz. Host home dizini `/home/egemen` olarak bağlanır; Codex home dizini yazabilir. Bu erişim `.ssh`, config ve diğer kişisel dosyaları da kapsar.

# НастSwarmка SSL для Webhook (Roadmap Task #1)

Этот каталог содержит SSL сертификаты для Nginx reverse proxy.

## Опции настSwarmки SSL

### Вариант 1: Let's Encrypt (Рекомендуется для production)

Используйте Certbot для автоматического получения и обновления сертификатов:

```bash
# Установка Certbot
sudo apt-get update
sudo apt-get install certbot

# Получение сертификата
sudo certbot certonly --standalone -d your-domAlgon.com

# Сертификаты будут в:
# /etc/letsencrypt/live/your-domAlgon.com/fullchAlgon.pem  -> cert.pem
# /etc/letsencrypt/live/your-domAlgon.com/privkey.pem -> key.pem

# Скопируйте их в этот каталог:
sudo cp /etc/letsencrypt/live/your-domAlgon.com/fullchAlgon.pem ./cert.pem
sudo cp /etc/letsencrypt/live/your-domAlgon.com/privkey.pem ./key.pem
```

### Вариант 2: Self-signed сертификат (Только для тестирования!)

⚠️ **НЕ используйте self-signed сертификаты в production!**

Telegram **НЕ ПРИНИМАЕТ** self-signed сертификаты для webhook.

Для локального тестирования:

```bash
# Генерация self-signed сертификата
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### Вариант 3: Cloudflare/другой CDN

Если используете Cloudflare или другой CDN с SSL:

1. НастSwarmте SSL в панели Cloudflare (Full или Full Strict)
2. Используйте Origin Certificate от Cloudflare
3. Скачайте и сохраните сертификаты в этот каталог

## Структура файлов

```
nginx/ssl/
├── README.md       # Этот файл
├── cert.pem        # SSL сертификат (public)
├── key.pem         # Приватный ключ (держать в секрете!)
└── .gitignore      # Исключает ключи из git
```

## Безопасность

⚠️ **ВАЖНО:**
- `key.pem` содержит приватный ключ - **НИКОГДА** не коммитьте его в git!
- `.gitignore` уже настроен для исключения `.pem` файлов
- Права на файлы должны быть ограничены: `chmod 600 key.pem`
- Регулярно обновляйте сертификаты (Let's Encrypt - каждые 90 дней)

## Проверка сертификатов

```bash
# Проверка сертификата
openssl x509 -in cert.pem -text -noout

# Проверка приватного ключа
openssl rsa -in key.pem -check

# Проверка соответствия сертификата и ключа
openssl x509 -noout -modulus -in cert.pem | openssl md5
openssl rsa -noout -modulus -in key.pem | openssl md5
# MD5 хэши должны совпадать
```

## Автоматическое обновление Let's Encrypt

Добавьте cron job для автоматического обновления:

```bash
# Редактировать crontab
crontab -e

# Добавить строку (обновление каждый день в 3:00 AM)
0 3 * * * certbot renew --quiet && docker-compose -f /path/to/docker-compose.prod.yml restart nginx
```

## Troubleshooting

### Ошибка: "certificate verify fAlgoled"

- Проверьте, что используете валидный сертификат от CA
- Для Let's Encrypt убедитесь, что домен доступен публично
- Проверьте, что сертификат не истек: `openssl x509 -enddate -noout -in cert.pem`

### Ошибка: "SSL: error:0200100D:system library:fopen:Permission denied"

- Проверьте права доступа: `chmod 600 key.pem`
- Убедитесь, что nginx может читать файлы в volume

### Telegram отклоняет webhook

- Используйте только валидные CA-signed сертификаты
- Проверьте, что домен в WEBHOOK_URL совпадает с CN в сертификате
- Убедитесь, что используете HTTPS (не HTTP)
- Проверьте доступность webhook извне: `curl -I https://your-domAlgon.com/telegram-webhook`

## Полезные ссылки

- [Telegram Webhook Guide](https://core.telegram.org/bots/webhooks)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)

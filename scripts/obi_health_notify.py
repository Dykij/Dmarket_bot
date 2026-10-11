#!/usr/bin/env python3
"""Отправка текста отчёта монитора в Telegram (только stdlib).

Использование:
  python3 -I -B obi_health_notify.py <файл_с_текстом> [--title ТЕКСТ] [--footer ТЕКСТ] [--dry]

Токен и chat id берутся из переменных окружения TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID
(в GitHub Actions -- из секретов репозитория). Значения нигде не печатаются.
TELEGRAM_API_BASE (по умолчанию https://api.telegram.org) нужен только для локальных тестов.
--dry: напечатать итоговое сообщение вместо отправки (секреты не нужны).

Сообщение: [title\n\n]<текст файла>[\n\nfooter], длина не больше 3900 символов (лимит Telegram
4096), лишнее обрезается с пометкой. Обычный текст, без разметки.
Повтор: до 3 попыток при сетевой ошибке или ответе 5xx/429, пауза 3 с.

Коды выхода: 0 -- отправлено (или --dry); 2 -- неверные аргументы или файл не прочитан;
3 -- секреты не заданы; 4 -- отправка не удалась.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

LIMIT = 3900
ATTEMPTS = 3
PAUSE = float(os.environ.get("TELEGRAM_RETRY_PAUSE", "3"))


def parse(argv):
    path, title, footer, dry = None, None, None, False
    it = iter(argv)
    for a in it:
        if a in ("--title", "--footer"):
            value = next(it, None)
            if value is None:
                return None
            if a == "--title":
                title = value
            else:
                footer = value
        elif a == "--dry":
            dry = True
        elif a.startswith("--"):
            return None
        elif path is None:
            path = a
        else:
            return None
    if path is None or title == "" or footer == "":
        return None
    return path, title, footer, dry


def build_message(body, title, footer):
    head = f"{title}\n\n" if title else ""
    tail = f"\n\n{footer}" if footer else ""
    room = LIMIT - len(head) - len(tail)
    body = body.strip()
    if len(body) > room:
        mark = "\n…(обрезано)"
        body = body[: max(room - len(mark), 0)].rstrip() + mark
    return head + body + tail


def send(token, chat_id, text, base):
    """Возвращает (успех, строка_для_лога). Токен в строку не попадает."""
    url = f"{base.rstrip('/')}/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    last = "нет ответа"
    for attempt in range(1, ATTEMPTS + 1):
        retry = False
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
            if payload.get("ok") is True:
                return True, "Telegram: отправлено"
            last = f"Telegram: ответ без ok ({str(payload.get('description', ''))[:120]})"
        except urllib.error.HTTPError as e:
            desc = ""
            try:
                desc = str(json.loads(e.read().decode("utf-8", "replace")).get("description", ""))
            except Exception:
                desc = ""
            last = f"Telegram: HTTP {e.code} {desc[:120]}".rstrip()
            retry = e.code >= 500 or e.code == 429
        except Exception as e:
            last = f"Telegram: сеть/разбор ({type(e).__name__})"
            retry = True
        if not retry or attempt == ATTEMPTS:
            break
        time.sleep(PAUSE)
    return False, last


def main():
    parsed = parse(sys.argv[1:])
    if parsed is None:
        print("нужно: <файл> [--title ТЕКСТ] [--footer ТЕКСТ] [--dry]", file=sys.stderr)
        return 2
    path, title, footer, dry = parsed
    try:
        with open(path, encoding="utf-8") as f:
            body = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"файл не прочитан ({type(e).__name__})", file=sys.stderr)
        return 2
    text = build_message(body, title, footer)
    if dry:
        print("--- DRY: сообщение не отправляется, вот его текст ---")
        print(text)
        print(f"--- длина {len(text)} ---")
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы", file=sys.stderr)
        return 3
    base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
    ok, msg = send(token, chat_id, text, base)
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())

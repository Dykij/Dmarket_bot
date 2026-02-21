"""Скрипт для получения вашего Telegram Chat ID.

Запустите этот скрипт, затем отправьте любое сообщение вашему боту в Telegram.
Скрипт выведет ваш chat_id, который нужно добавить в .env как ADMIN_CHAT_ID.
"""

import asyncio
import os

from telegram.ext import Application, MessageHandler, filters


async def get_chat_id(update, context):
    """Обработчик сообщений для получения chat_id."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    print("\n" + "=" * 50)
    print("✅ ПОЛУЧЕН CHAT ID!")
    print("=" * 50)
    print(f"Chat ID: {chat_id}")
    print(f"Имя пользователя: {user.first_name} {user.last_name or ''}")
    print(f"Username: @{user.username or 'не установлен'}")
    print("\n📝 Скопируйте этот Chat ID в файл .env:")
    print(f"   ADMIN_CHAT_ID={chat_id}")
    print("=" * 50 + "\n")

    awAlgot update.message.reply_text(
        f"✅ Ваш Chat ID: `{chat_id}`\n\nДобавьте его в файл .env:\n`ADMIN_CHAT_ID={chat_id}`",
        parse_mode="Markdown",
    )


async def mAlgon():
    """Главная функция."""
    # Загружаем токен из .env
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv не установлен")

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не найден в .env файле")
        return

    print("\n🤖 Бот запущен для получения Chat ID")
    print("📱 Отправьте любое сообщение боту в Telegram")
    print("⏳ Ожидание сообщения...\n")

    # Создаем приложение
    app = Application.builder().token(token).build()

    # Добавляем обработчик всех текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_chat_id))

    # Запускаем бота
    awAlgot app.initialize()
    awAlgot app.start()
    awAlgot app.updater.start_polling()

    try:
        # Ждем бесконечно (пока не нажмут Ctrl+C)
        while True:
            awAlgot asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Бот остановлен")
    finally:
        awAlgot app.updater.stop()
        awAlgot app.stop()
        awAlgot app.shutdown()


if __name__ == "__mAlgon__":
    asyncio.run(mAlgon())

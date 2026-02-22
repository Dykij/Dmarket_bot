"""
Algo Integration Handler для Telegram бота.

Интегрирует локальные Model (Ollama) и MCP сервер для Algo-помощника.
Поддержка нескольких моделей: Llama 3.1, Qwen 2.5, Mistral, Gemma 2.
"""

import json
from enum import StrEnum
from typing import Any

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

try:
    import httpx

    HTTPX_AVAlgoLABLE = True
except ImportError:
    HTTPX_AVAlgoLABLE = False


logger = structlog.get_logger(__name__)


class AlgoModel(StrEnum):
    """Поддерживаемые Algo модели."""

    LLAMA_31_8B = "llama3.1:8b"
    LLAMA_31_70B = "llama3.1:70b"
    QWEN_25_7B = "qwen2.5:7b"
    QWEN_25_14B = "qwen2.5:14b"
    MISTRAL_7B = "mistral:7b"
    GEMMA2_9B = "gemma2:9b"
    CODELLAMA_13B = "codellama:13b"


# Рекомендации по моделям для разных задач
MODEL_RECOMMENDATIONS = {
    "general_chat": {
        "model": AlgoModel.LLAMA_31_8B,
        "reason": "Универсальная модель для чата, хороший баланс скорости и качества",
        "vram_required": "6-8 GB",
        "tokens_per_sec_cpu": "20-40",
    },
    "market_analysis": {
        "model": AlgoModel.QWEN_25_7B,
        "reason": "Отличные аналитические способности, поддержка чисел и данных",
        "vram_required": "5-7 GB",
        "tokens_per_sec_cpu": "25-45",
    },
    "trading_advice": {
        "model": AlgoModel.MISTRAL_7B,
        "reason": "Быстрые ответы, хорошая логика для торговых решений",
        "vram_required": "5-6 GB",
        "tokens_per_sec_cpu": "30-50",
    },
    "coding_automation": {
        "model": AlgoModel.CODELLAMA_13B,
        "reason": "Специализирована для кода и автоматизации",
        "vram_required": "10-12 GB",
        "tokens_per_sec_cpu": "15-25",
    },
}

# Системный промпт для DMarket бота
DMARKET_SYSTEM_Config = """Ты - Algo-помощник для DMarket Trading Bot.
Ты помогаешь пользователям:
1. Анализировать рынок CS:GO, Dota 2, Rust, TF2
2. Находить арбитражные возможности
3. Давать рекомендации по покупке/продаже
4. Объяснять торговые стратегии
5. Помогать с настSwarmкой бота

Комиссии площадок:
- DMarket: 7%
- Waxpeer: 6%
- Steam Market: 15%

Уровни арбитража:
- boost: $0.50-$3 (начинающие)
- standard: $3-$10 (стандарт)
- medium: $10-$30 (средний)
- advanced: $30-$100 (продвинутый)
- pro: $100+ (профессионал)

Отвечай на русском языке, кратко и по делу.
Если нужна информация о ценах или предметах - используй доступные инструменты."""


class AlgoIntegrationHandler:
    """Обработчик Algo интеграции."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        default_model: str = "llama3.1:8b",
    ):
        """
        Инициализация Algo обработчика.

        Args:
            ollama_url: URL Ollama сервера
            default_model: Модель по умолчанию
        """
        self.ollama_url = ollama_url
        self.default_model = default_model
        self.conversation_history: dict[int, list[dict]] = {}
        self.user_models: dict[int, str] = {}
        self._mcp_server = None

    async def check_ollama_status(self) -> dict[str, Any]:
        """Проверить статус Ollama сервера."""
        if not HTTPX_AVAlgoLABLE:
            return {"avAlgolable": False, "error": "httpx not installed"}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return {
                        "avAlgolable": True,
                        "models": models,
                        "url": self.ollama_url,
                    }
                return {"avAlgolable": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"avAlgolable": False, "error": str(e)}

    async def list_avAlgolable_models(self) -> list[str]:
        """Получить список доступных моделей."""
        status = await self.check_ollama_status()
        return status.get("models", [])

    async def chat_with_Algo(
        self,
        user_id: int,
        message: str,
        model: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Отправить сообщение Algo.

        Args:
            user_id: ID пользователя
            message: Сообщение
            model: Модель (опционально)
            context: Дополнительный контекст (опционально)

        Returns:
            Ответ Algo
        """
        if not HTTPX_AVAlgoLABLE:
            return "❌ httpx не установлен. Установите: pip install httpx"

        model = model or self.user_models.get(user_id) or self.default_model

        # Инициализация истории разговора
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        # Добавляем контекст если есть
        enhanced_message = message
        if context:
            context_str = json.dumps(context, ensure_ascii=False, indent=2)
            enhanced_message = f"{message}\n\nКонтекст:\n{context_str}"

        # Добавляем сообщение пользователя
        self.conversation_history[user_id].append(
            {
                "role": "user",
                "content": enhanced_message,
            }
        )

        # Ограничиваем историю последними 10 сообщениями
        if len(self.conversation_history[user_id]) > 20:
            self.conversation_history[user_id] = self.conversation_history[user_id][
                -20:
            ]

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": DMARKET_SYSTEM_Config},
                            *self.conversation_history[user_id],
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "num_predict": 1024,
                        },
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    Algo_response = data.get("message", {}).get("content", "Нет ответа")

                    # Добавляем ответ в историю
                    self.conversation_history[user_id].append(
                        {
                            "role": "assistant",
                            "content": Algo_response,
                        }
                    )

                    return Algo_response
                return f"❌ Ошибка Ollama: HTTP {response.status_code}"

        except httpx.TimeoutException:
            return "❌ Таймаут запроса к Ollama. Попробуйте позже."
        except Exception as e:
            logger.error("Algo_chat_error", error=str(e), exc_info=True)
            return f"❌ Ошибка: {e!s}"

    def clear_history(self, user_id: int) -> None:
        """Очистить историю разговора."""
        if user_id in self.conversation_history:
            self.conversation_history[user_id] = []

    def set_user_model(self, user_id: int, model: str) -> None:
        """Установить модель для пользователя."""
        self.user_models[user_id] = model


# Глобальный экземпляр
_Algo_handler: AlgoIntegrationHandler | None = None


def get_Algo_handler() -> AlgoIntegrationHandler:
    """Получить Algo handler."""
    global _Algo_handler
    if _Algo_handler is None:
        _Algo_handler = AlgoIntegrationHandler()
    return _Algo_handler


# === Telegram Handlers ===


async def Algo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /Algo - главное меню Algo."""
    if not update.message:
        return

    handler = get_Algo_handler()
    status = await handler.check_ollama_status()

    keyboard = [
        [
            InlineKeyboardButton("💬 Чат с Algo", callback_data="Algo_chat"),
            InlineKeyboardButton("🔧 НастSwarmки", callback_data="Algo_settings"),
        ],
        [
            InlineKeyboardButton("📊 Анализ рынка", callback_data="Algo_analyze_market"),
            InlineKeyboardButton("💡 Рекомендации", callback_data="Algo_recommendations"),
        ],
        [
            InlineKeyboardButton("📋 Статус", callback_data="Algo_status"),
            InlineKeyboardButton("🔄 Очистить историю", callback_data="Algo_clear"),
        ],
    ]

    status_emoji = "✅" if status.get("avAlgolable") else "❌"
    models_count = len(status.get("models", []))

    text = f"""🤖 **Algo Помощник DMarket Bot**

**Статус Ollama:** {status_emoji}
**Моделей доступно:** {models_count}
**URL:** `{handler.ollama_url}`

**Возможности:**
• 💬 Чат о трейдинге и рынке
• 📊 Анализ рыночных данных
• 💡 Рекомендации по арбитражу
• 🔮 Прогнозирование трендов

Выберите действие:"""

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def Algo_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /Algo_chat - чат с Algo."""
    if not update.message:
        return

    # Получаем текст после команды
    if context.args:
        message = " ".join(context.args)
    else:
        await update.message.reply_text(
            "💬 **Algo Чат**\n\n"
            "Отправьте сообщение после команды:\n"
            "`/Algo_chat Какие сейчас лучшие арбитражные возможности?`\n\n"
            "Или просто напишите вопрос:",
            parse_mode="Markdown",
        )
        return

    handler = get_Algo_handler()
    user_id = update.effective_user.id

    # Показываем что печатаем
    await update.message.chat.send_action("typing")

    response = await handler.chat_with_Algo(user_id, message)

    await update.message.reply_text(
        f"🤖 **Algo:**\n\n{response}",
        parse_mode="Markdown",
    )


async def Algo_models_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /Algo_models - список моделей."""
    if not update.message:
        return

    handler = get_Algo_handler()
    models = await handler.list_avAlgolable_models()

    if not models:
        await update.message.reply_text(
            "❌ **Ollama недоступна или нет установленных моделей**\n\n"
            "Установите модель:\n"
            "```bash\n"
            "ollama pull llama3.1:8b\n"
            "```",
            parse_mode="Markdown",
        )
        return

    text = "📋 **Доступные Algo модели:**\n\n"
    for model in models:
        text += f"• `{model}`\n"

    text += "\n**Рекомендованные модели для вашего железа:**\n"
    text += "(Ryzen 7 5700X, 32GB RAM, RX 6600 8GB VRAM)\n\n"

    text += "🏆 **Лучший выбор:** `llama3.1:8b` или `qwen2.5:7b`\n"
    text += "⚡ **Для скорости:** `mistral:7b`\n"
    text += "📊 **Для анализа:** `qwen2.5:14b` (Q4 квантизация)\n\n"

    text += "Установить модель:\n"
    text += "`/Algo_set_model <model_name>`"

    await update.message.reply_text(text, parse_mode="Markdown")


async def Algo_set_model_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик команды /Algo_set_model - установить модель."""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Укажите модель: `/Algo_set_model llama3.1:8b`",
            parse_mode="Markdown",
        )
        return

    model = context.args[0]
    handler = get_Algo_handler()
    user_id = update.effective_user.id

    handler.set_user_model(user_id, model)

    await update.message.reply_text(
        f"✅ Модель установлена: `{model}`",
        parse_mode="Markdown",
    )


async def Algo_analyze_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик команды /Algo_analyze - анализ рынка с Algo."""
    if not update.message:
        return

    # Получаем игру из аргументов
    game = context.args[0] if context.args else "csgo"

    await update.message.chat.send_action("typing")

    handler = get_Algo_handler()
    user_id = update.effective_user.id

    # Формируем запрос к Algo
    Config = f"""Проанализируй текущую ситуацию на рынке {game.upper()}:
1. Общие тренды
2. Рекомендации по покупке/продаже
3. Потенциальные арбитражные возможности
4. Риски

Дай краткий анализ на основе твоих знаний о рынке скинов."""

    response = await handler.chat_with_Algo(user_id, Config)

    await update.message.reply_text(
        f"📊 **Algo Анализ рынка {game.upper()}:**\n\n{response}",
        parse_mode="Markdown",
    )


async def Algo_recommend_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик команды /Algo_recommend - рекомендации модели."""
    if not update.message:
        return

    text = """🧠 **Рекомендации по выбору Algo модели**

**Ваше оборудование:**
• CPU: Ryzen 7 5700X (8 ядер, 16 потоков)
• RAM: 32 ГБ
• GPU: Radeon RX 6600 (8 ГБ VRAM)

**Лучшие модели для локального запуска:**

🥇 **Llama 3.1 8B** (Рекомендуется)
• VRAM: 6-8 GB (Q4 квантизация)
• CPU: 20-40 токенов/с
• Универсальная, хорошо говорит по-русски

🥈 **Qwen 2.5 7B** (Альтернатива)
• VRAM: 5-7 GB
• CPU: 25-45 токенов/с
• Отличная для анализа данных

🥉 **Mistral 7B** (Для скорости)
• VRAM: 5-6 GB
• CPU: 30-50 токенов/с
• Быстрые ответы

**Установка через Ollama:**
```bash
# Установка Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Скачивание модели
ollama pull llama3.1:8b

# Запуск
ollama serve
```

**Для AMD RX 6600:**
```bash
# Ubuntu с ROCm
HSA_OVERRIDE_GFX_VERSION=10.3.0 ollama serve
```

**Альтернативы:**
• **LM Studio** - GUI для Windows, поддержка Vulkan
• **llama.cpp** - OpenAlgo-совместимый API
• **LocalAlgo** - полная эмуляция OpenAlgo API"""

    await update.message.reply_text(text, parse_mode="Markdown")


async def Algo_status_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback для статуса Algo."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    handler = get_Algo_handler()
    status = await handler.check_ollama_status()

    if status.get("avAlgolable"):
        models = status.get("models", [])
        text = f"""✅ **Ollama доступна**

**URL:** `{handler.ollama_url}`
**Моделей:** {len(models)}

**Установленные модели:**
"""
        for model in models[:10]:
            text += f"• `{model}`\n"

        if len(models) > 10:
            text += f"... и ещё {len(models) - 10}"
    else:
        text = f"""❌ **Ollama недоступна**

**Ошибка:** {status.get('error', 'Unknown')}

**Как запустить:**
1. Установите Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Скачайте модель: `ollama pull llama3.1:8b`
3. Запустите: `ollama serve`"""

    await query.edit_message_text(text, parse_mode="Markdown")


async def Algo_clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback для очистки истории."""
    query = update.callback_query
    if not query:
        return

    await query.answer("История очищена")

    handler = get_Algo_handler()
    user_id = update.effective_user.id
    handler.clear_history(user_id)

    await query.edit_message_text(
        "🗑️ История разговора очищена.\n\n" "Используйте /Algo для нового разговора.",
        parse_mode="Markdown",
    )


# Регистрация обработчиков
def register_Algo_handlers(application) -> None:
    """Регистрация Algo обработчиков."""
    from telegram.ext import CallbackQueryHandler, CommandHandler

    application.add_handler(CommandHandler("Algo", Algo_command))
    application.add_handler(CommandHandler("Algo_chat", Algo_chat_command))
    application.add_handler(CommandHandler("Algo_models", Algo_models_command))
    application.add_handler(CommandHandler("Algo_set_model", Algo_set_model_command))
    application.add_handler(CommandHandler("Algo_analyze", Algo_analyze_command))
    application.add_handler(CommandHandler("Algo_recommend", Algo_recommend_command))

    application.add_handler(
        CallbackQueryHandler(Algo_status_callback, pattern="^Algo_status$")
    )
    application.add_handler(
        CallbackQueryHandler(Algo_clear_callback, pattern="^Algo_clear$")
    )

    logger.info("Algo_handlers_registered")

"""
Тесты для AI Integration Handler.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAIIntegrationHandler:
    """Тесты для AIIntegrationHandler."""

    def test_model_recommendations_exist(self):
        """Тест наличия рекомендаций по моделям."""
        from src.telegram_bot.handlers.ai_integration_handler import MODEL_RECOMMENDATIONS

        assert "general_chat" in MODEL_RECOMMENDATIONS
        assert "market_analysis" in MODEL_RECOMMENDATIONS
        assert "trading_advice" in MODEL_RECOMMENDATIONS
        assert "coding_automation" in MODEL_RECOMMENDATIONS

    def test_ai_models_enum(self):
        """Тест перечисления моделей."""
        from src.telegram_bot.handlers.ai_integration_handler import AIModel

        assert AIModel.LLAMA_31_8B == "llama3.1:8b"
        assert AIModel.QWEN_25_7B == "qwen2.5:7b"
        assert AIModel.MISTRAL_7B == "mistral:7b"

    def test_system_prompt_exists(self):
        """Тест наличия системного промпта."""
        from src.telegram_bot.handlers.ai_integration_handler import DMARKET_SYSTEM_PROMPT

        assert "DMarket" in DMARKET_SYSTEM_PROMPT
        assert "7%" in DMARKET_SYSTEM_PROMPT  # DMarket commission
        assert "6%" in DMARKET_SYSTEM_PROMPT  # Waxpeer commission

    def test_handler_initialization(self):
        """Тест инициализации обработчика."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        handler = AIIntegrationHandler(
            ollama_url="http://localhost:11434",
            default_model="llama3.1:8b",
        )

        assert handler.ollama_url == "http://localhost:11434"
        assert handler.default_model == "llama3.1:8b"
        assert handler.conversation_history == {}
        assert handler.user_models == {}

    def test_get_ai_handler_singleton(self):
        """Тест синглтона обработчика."""
        from src.telegram_bot.handlers.ai_integration_handler import get_ai_handler

        handler1 = get_ai_handler()
        handler2 = get_ai_handler()

        assert handler1 is handler2

    def test_clear_history(self):
        """Тест очистки истории."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        handler = AIIntegrationHandler()
        handler.conversation_history[123] = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "response"},
        ]

        handler.clear_history(123)

        assert handler.conversation_history[123] == []

    def test_set_user_model(self):
        """Тест установки модели для пользователя."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        handler = AIIntegrationHandler()
        handler.set_user_model(123, "qwen2.5:7b")

        assert handler.user_models[123] == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_check_ollama_status_no_httpx(self):
        """Тест проверки статуса без httpx."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.HTTPX_AVAILABLE", False
        ):
            handler = AIIntegrationHandler()
            status = await handler.check_ollama_status()

            assert status["available"] is False
            assert "httpx not installed" in status["error"]

    @pytest.mark.asyncio
    async def test_check_ollama_status_success(self):
        """Тест успешной проверки статуса."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "qwen2.5:7b"},
            ]
        }

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.HTTPX_AVAILABLE", True
        ), patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            handler = AIIntegrationHandler()
            status = await handler.check_ollama_status()

            assert status["available"] is True
            assert "llama3.1:8b" in status["models"]
            assert "qwen2.5:7b" in status["models"]

    @pytest.mark.asyncio
    async def test_list_available_models(self):
        """Тест получения списка моделей."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        handler = AIIntegrationHandler()

        with patch.object(
            handler,
            "check_ollama_status",
            return_value={"available": True, "models": ["llama3.1:8b", "mistral:7b"]},
        ):
            models = await handler.list_available_models()

            assert "llama3.1:8b" in models
            assert "mistral:7b" in models

    @pytest.mark.asyncio
    async def test_chat_with_ai_no_httpx(self):
        """Тест чата без httpx."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.HTTPX_AVAILABLE", False
        ):
            handler = AIIntegrationHandler()
            response = await handler.chat_with_ai(123, "Hello")

            assert "httpx" in response.lower()

    @pytest.mark.asyncio
    async def test_chat_with_ai_success(self):
        """Тест успешного чата."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Test AI response"}
        }

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.HTTPX_AVAILABLE", True
        ), patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            handler = AIIntegrationHandler()
            response = await handler.chat_with_ai(123, "Test message")

            assert response == "Test AI response"
            assert len(handler.conversation_history[123]) == 2

    @pytest.mark.asyncio
    async def test_conversation_history_limit(self):
        """Тест ограничения истории разговора."""
        from src.telegram_bot.handlers.ai_integration_handler import AIIntegrationHandler

        handler = AIIntegrationHandler()

        # Добавляем 25 сообщений
        handler.conversation_history[123] = [
            {"role": "user", "content": f"msg{i}"} for i in range(25)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "response"}}

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.HTTPX_AVAILABLE", True
        ), patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await handler.chat_with_ai(123, "new message")

            # После добавления нового сообщения должно быть обрезано до 20
            assert len(handler.conversation_history[123]) <= 22


class TestAITelegramCommands:
    """Тесты для Telegram команд AI."""

    @pytest.mark.asyncio
    async def test_ai_command(self):
        """Тест команды /ai."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.get_ai_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_handler.check_ollama_status = AsyncMock(
                return_value={"available": True, "models": ["llama3.1:8b"]}
            )
            mock_handler.ollama_url = "http://localhost:11434"
            mock_get.return_value = mock_handler

            await ai_command(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args
            assert "AI Помощник" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_ai_chat_command_no_args(self):
        """Тест команды /ai_chat без аргументов."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_chat_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await ai_chat_command(update, context)

        update.message.reply_text.assert_called_once()
        assert "AI Чат" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_ai_models_command_no_models(self):
        """Тест команды /ai_models без моделей."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_models_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.get_ai_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_handler.list_available_models = AsyncMock(return_value=[])
            mock_get.return_value = mock_handler

            await ai_models_command(update, context)

            assert "недоступна" in update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_ai_set_model_command_no_args(self):
        """Тест команды /ai_set_model без аргументов."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_set_model_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await ai_set_model_command(update, context)

        assert "Укажите модель" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_ai_set_model_command_with_model(self):
        """Тест команды /ai_set_model с моделью."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_set_model_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        context = MagicMock()
        context.args = ["qwen2.5:7b"]

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.get_ai_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_get.return_value = mock_handler

            await ai_set_model_command(update, context)

            mock_handler.set_user_model.assert_called_once_with(123, "qwen2.5:7b")
            assert "установлена" in update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_ai_recommend_command(self):
        """Тест команды /ai_recommend."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_recommend_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        await ai_recommend_command(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "Ryzen 7 5700X" in call_text
        assert "llama3.1:8b" in call_text.lower() or "Llama 3.1 8B" in call_text

    @pytest.mark.asyncio
    async def test_ai_clear_callback(self):
        """Тест callback очистки истории."""
        from src.telegram_bot.handlers.ai_integration_handler import ai_clear_callback

        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch(
            "src.telegram_bot.handlers.ai_integration_handler.get_ai_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_get.return_value = mock_handler

            await ai_clear_callback(update, context)

            mock_handler.clear_history.assert_called_once_with(123)
            query.answer.assert_called_once()


class TestModelRecommendations:
    """Тесты рекомендаций по моделям."""

    def test_llama_recommended_for_general(self):
        """Тест что Llama рекомендуется для общего чата."""
        from src.telegram_bot.handlers.ai_integration_handler import (
            MODEL_RECOMMENDATIONS,
            AIModel,
        )

        rec = MODEL_RECOMMENDATIONS["general_chat"]
        assert rec["model"] == AIModel.LLAMA_31_8B

    def test_qwen_recommended_for_analysis(self):
        """Тест что Qwen рекомендуется для анализа."""
        from src.telegram_bot.handlers.ai_integration_handler import (
            MODEL_RECOMMENDATIONS,
            AIModel,
        )

        rec = MODEL_RECOMMENDATIONS["market_analysis"]
        assert rec["model"] == AIModel.QWEN_25_7B

    def test_all_recommendations_have_required_fields(self):
        """Тест что все рекомендации имеют необходимые поля."""
        from src.telegram_bot.handlers.ai_integration_handler import MODEL_RECOMMENDATIONS

        for task, rec in MODEL_RECOMMENDATIONS.items():
            assert "model" in rec, f"Missing model for {task}"
            assert "reason" in rec, f"Missing reason for {task}"
            assert "vram_required" in rec, f"Missing vram_required for {task}"
            assert "tokens_per_sec_cpu" in rec, f"Missing tokens_per_sec_cpu for {task}"

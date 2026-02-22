"""
Тесты для Algo Integration Handler.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAlgoIntegrationHandler:
    """Тесты для AlgoIntegrationHandler."""

    def test_model_recommendations_exist(self):
        """Тест наличия рекомендаций по моделям."""
        from src.telegram_bot.handlers.Algo_integration_handler import MODEL_RECOMMENDATIONS

        assert "general_chat" in MODEL_RECOMMENDATIONS
        assert "market_analysis" in MODEL_RECOMMENDATIONS
        assert "trading_advice" in MODEL_RECOMMENDATIONS
        assert "coding_automation" in MODEL_RECOMMENDATIONS

    def test_Algo_models_enum(self):
        """Тест перечисления моделей."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoModel

        assert AlgoModel.LLAMA_31_8B == "llama3.1:8b"
        assert AlgoModel.QWEN_25_7B == "qwen2.5:7b"
        assert AlgoModel.MISTRAL_7B == "mistral:7b"

    def test_system_Config_exists(self):
        """Тест наличия системного промпта."""
        from src.telegram_bot.handlers.Algo_integration_handler import DMARKET_SYSTEM_Config

        assert "DMarket" in DMARKET_SYSTEM_Config
        assert "7%" in DMARKET_SYSTEM_Config  # DMarket commission
        assert "6%" in DMARKET_SYSTEM_Config  # Waxpeer commission

    def test_handler_initialization(self):
        """Тест инициализации обработчика."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        handler = AlgoIntegrationHandler(
            ollama_url="http://localhost:11434",
            default_model="llama3.1:8b",
        )

        assert handler.ollama_url == "http://localhost:11434"
        assert handler.default_model == "llama3.1:8b"
        assert handler.conversation_history == {}
        assert handler.user_models == {}

    def test_get_Algo_handler_singleton(self):
        """Тест синглтона обработчика."""
        from src.telegram_bot.handlers.Algo_integration_handler import get_Algo_handler

        handler1 = get_Algo_handler()
        handler2 = get_Algo_handler()

        assert handler1 is handler2

    def test_clear_history(self):
        """Тест очистки истории."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        handler = AlgoIntegrationHandler()
        handler.conversation_history[123] = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "response"},
        ]

        handler.clear_history(123)

        assert handler.conversation_history[123] == []

    def test_set_user_model(self):
        """Тест установки модели для пользователя."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        handler = AlgoIntegrationHandler()
        handler.set_user_model(123, "qwen2.5:7b")

        assert handler.user_models[123] == "qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_check_ollama_status_no_httpx(self):
        """Тест проверки статуса без httpx."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.HTTPX_AVAlgoLABLE", False
        ):
            handler = AlgoIntegrationHandler()
            status = await handler.check_ollama_status()

            assert status["avAlgolable"] is False
            assert "httpx not installed" in status["error"]

    @pytest.mark.asyncio
    async def test_check_ollama_status_success(self):
        """Тест успешной проверки статуса."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "qwen2.5:7b"},
            ]
        }

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.HTTPX_AVAlgoLABLE", True
        ), patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            handler = AlgoIntegrationHandler()
            status = await handler.check_ollama_status()

            assert status["avAlgolable"] is True
            assert "llama3.1:8b" in status["models"]
            assert "qwen2.5:7b" in status["models"]

    @pytest.mark.asyncio
    async def test_list_avAlgolable_models(self):
        """Тест получения списка моделей."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        handler = AlgoIntegrationHandler()

        with patch.object(
            handler,
            "check_ollama_status",
            return_value={"avAlgolable": True, "models": ["llama3.1:8b", "mistral:7b"]},
        ):
            models = await handler.list_avAlgolable_models()

            assert "llama3.1:8b" in models
            assert "mistral:7b" in models

    @pytest.mark.asyncio
    async def test_chat_with_Algo_no_httpx(self):
        """Тест чата без httpx."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.HTTPX_AVAlgoLABLE", False
        ):
            handler = AlgoIntegrationHandler()
            response = await handler.chat_with_Algo(123, "Hello")

            assert "httpx" in response.lower()

    @pytest.mark.asyncio
    async def test_chat_with_Algo_success(self):
        """Тест успешного чата."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Test Algo response"}
        }

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.HTTPX_AVAlgoLABLE", True
        ), patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            handler = AlgoIntegrationHandler()
            response = await handler.chat_with_Algo(123, "Test message")

            assert response == "Test Algo response"
            assert len(handler.conversation_history[123]) == 2

    @pytest.mark.asyncio
    async def test_conversation_history_limit(self):
        """Тест ограничения истории разговора."""
        from src.telegram_bot.handlers.Algo_integration_handler import AlgoIntegrationHandler

        handler = AlgoIntegrationHandler()

        # Добавляем 25 сообщений
        handler.conversation_history[123] = [
            {"role": "user", "content": f"msg{i}"} for i in range(25)
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "response"}}

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.HTTPX_AVAlgoLABLE", True
        ), patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            await handler.chat_with_Algo(123, "new message")

            # После добавления нового сообщения должно быть обрезано до 20
            assert len(handler.conversation_history[123]) <= 22


class TestAlgoTelegramCommands:
    """Тесты для Telegram команд Algo."""

    @pytest.mark.asyncio
    async def test_Algo_command(self):
        """Тест команды /Algo."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.get_Algo_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_handler.check_ollama_status = AsyncMock(
                return_value={"avAlgolable": True, "models": ["llama3.1:8b"]}
            )
            mock_handler.ollama_url = "http://localhost:11434"
            mock_get.return_value = mock_handler

            await Algo_command(update, context)

            update.message.reply_text.assert_called_once()
            call_args = update.message.reply_text.call_args
            assert "Algo Помощник" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_Algo_chat_command_no_args(self):
        """Тест команды /Algo_chat без аргументов."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_chat_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await Algo_chat_command(update, context)

        update.message.reply_text.assert_called_once()
        assert "Algo Чат" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_Algo_models_command_no_models(self):
        """Тест команды /Algo_models без моделей."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_models_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.get_Algo_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_handler.list_avAlgolable_models = AsyncMock(return_value=[])
            mock_get.return_value = mock_handler

            await Algo_models_command(update, context)

            assert "недоступна" in update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_Algo_set_model_command_no_args(self):
        """Тест команды /Algo_set_model без аргументов."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_set_model_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await Algo_set_model_command(update, context)

        assert "Укажите модель" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_Algo_set_model_command_with_model(self):
        """Тест команды /Algo_set_model с моделью."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_set_model_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        context = MagicMock()
        context.args = ["qwen2.5:7b"]

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.get_Algo_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_get.return_value = mock_handler

            await Algo_set_model_command(update, context)

            mock_handler.set_user_model.assert_called_once_with(123, "qwen2.5:7b")
            assert "установлена" in update.message.reply_text.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_Algo_recommend_command(self):
        """Тест команды /Algo_recommend."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_recommend_command

        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        await Algo_recommend_command(update, context)

        call_text = update.message.reply_text.call_args[0][0]
        assert "Ryzen 7 5700X" in call_text
        assert "llama3.1:8b" in call_text.lower() or "Llama 3.1 8B" in call_text

    @pytest.mark.asyncio
    async def test_Algo_clear_callback(self):
        """Тест callback очистки истории."""
        from src.telegram_bot.handlers.Algo_integration_handler import Algo_clear_callback

        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()

        update = MagicMock()
        update.callback_query = query
        update.effective_user = MagicMock()
        update.effective_user.id = 123

        context = MagicMock()

        with patch(
            "src.telegram_bot.handlers.Algo_integration_handler.get_Algo_handler"
        ) as mock_get:
            mock_handler = MagicMock()
            mock_get.return_value = mock_handler

            await Algo_clear_callback(update, context)

            mock_handler.clear_history.assert_called_once_with(123)
            query.answer.assert_called_once()


class TestModelRecommendations:
    """Тесты рекомендаций по моделям."""

    def test_llama_recommended_for_general(self):
        """Тест что Llama рекомендуется для общего чата."""
        from src.telegram_bot.handlers.Algo_integration_handler import (
            MODEL_RECOMMENDATIONS,
            AlgoModel,
        )

        rec = MODEL_RECOMMENDATIONS["general_chat"]
        assert rec["model"] == AlgoModel.LLAMA_31_8B

    def test_qwen_recommended_for_analysis(self):
        """Тест что Qwen рекомендуется для анализа."""
        from src.telegram_bot.handlers.Algo_integration_handler import (
            MODEL_RECOMMENDATIONS,
            AlgoModel,
        )

        rec = MODEL_RECOMMENDATIONS["market_analysis"]
        assert rec["model"] == AlgoModel.QWEN_25_7B

    def test_all_recommendations_have_required_fields(self):
        """Тест что все рекомендации имеют необходимые поля."""
        from src.telegram_bot.handlers.Algo_integration_handler import MODEL_RECOMMENDATIONS

        for task, rec in MODEL_RECOMMENDATIONS.items():
            assert "model" in rec, f"Missing model for {task}"
            assert "reason" in rec, f"Missing reason for {task}"
            assert "vram_required" in rec, f"Missing vram_required for {task}"
            assert "tokens_per_sec_cpu" in rec, f"Missing tokens_per_sec_cpu for {task}"

"""
Comprehensive tests for Llama 3.1 8B Integration.

Тесты проверяют:
1. Инициализацию и конфигурацию
2. Доступность Ollama и модели
3. Все типы задач (market_analysis, price_prediction, etc.)
4. Обработку ошибок
5. Статистику использования
6. Кэширование и производительность
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Импортируем модуль
from src.ml.llama_integration import (
    TASK_PROMPTS,
    LlamaConfig,
    LlamaIntegration,
    LlamaResponse,
    LlamaTaskType,
    get_llama,
    init_llama,
)


class TestLlamaConfig:
    """Тесты конфигурации Llama."""
    
    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        config = LlamaConfig()
        
        assert config.model_name == "llama3.1:8b"
        assert config.ollama_url == "http://localhost:11434"
        assert config.temperature == 0.7
        assert config.top_p == 0.9
        assert config.max_tokens == 1024
        assert config.timeout == 120.0
        assert config.quantization == "Q4_K_M"
        assert config.context_length == 8192
        assert config.min_vram_gb == 6
        assert config.recommended_vram_gb == 8
    
    def test_custom_config(self):
        """Тест пользовательской конфигурации."""
        config = LlamaConfig(
            model_name="qwen2.5:7b",
            ollama_url="http://192.168.1.100:11434",
            temperature=0.5,
            max_tokens=2048,
        )
        
        assert config.model_name == "qwen2.5:7b"
        assert config.ollama_url == "http://192.168.1.100:11434"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048


class TestLlamaResponse:
    """Тесты ответа Llama."""
    
    def test_successful_response(self):
        """Тест успешного ответа."""
        response = LlamaResponse(
            success=True,
            response="Анализ рынка показывает восходящий тренд.",
            task_type=LlamaTaskType.MARKET_ANALYSIS,
            tokens_used=150,
            processing_time_ms=2500.0,
        )
        
        assert response.success is True
        assert "восходящий тренд" in response.response
        assert response.task_type == LlamaTaskType.MARKET_ANALYSIS
        assert response.tokens_used == 150
        assert response.processing_time_ms == 2500.0
        assert response.error is None
    
    def test_failed_response(self):
        """Тест неудачного ответа."""
        response = LlamaResponse(
            success=False,
            response="",
            task_type=LlamaTaskType.GENERAL_CHAT,
            error="Connection refused",
        )
        
        assert response.success is False
        assert response.response == ""
        assert response.error == "Connection refused"


class TestLlamaTaskType:
    """Тесты типов задач."""
    
    def test_all_task_types_have_prompts(self):
        """Проверяем что для всех типов задач есть промпты."""
        for task_type in LlamaTaskType:
            assert task_type in TASK_PROMPTS, f"Missing prompt for {task_type}"
    
    def test_task_type_values(self):
        """Тест значений типов задач."""
        assert LlamaTaskType.MARKET_ANALYSIS == "market_analysis"
        assert LlamaTaskType.PRICE_PREDICTION == "price_prediction"
        assert LlamaTaskType.ARBITRAGE_RECOMMENDATION == "arbitrage_recommendation"
        assert LlamaTaskType.TRADING_ADVICE == "trading_advice"
        assert LlamaTaskType.GENERAL_CHAT == "general_chat"
        assert LlamaTaskType.ITEM_EVALUATION == "item_evaluation"
        assert LlamaTaskType.RISK_ASSESSMENT == "risk_assessment"


class TestLlamaIntegrationInit:
    """Тесты инициализации LlamaIntegration."""
    
    def test_default_initialization(self):
        """Тест инициализации по умолчанию."""
        llama = LlamaIntegration()
        
        assert llama.config.model_name == "llama3.1:8b"
        assert llama._client is None
        assert llama._is_available is None
        assert llama.stats["total_requests"] == 0
    
    def test_custom_config_initialization(self):
        """Тест инициализации с пользовательской конфигурацией."""
        config = LlamaConfig(model_name="mistral:7b")
        llama = LlamaIntegration(config)
        
        assert llama.config.model_name == "mistral:7b"


class TestLlamaIntegrationAvailability:
    """Тесты проверки доступности."""
    
    @pytest.mark.asyncio
    async def test_check_availability_success(self):
        """Тест успешной проверки доступности."""
        llama = LlamaIntegration()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "mistral:7b"},
            ]
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value = mock_client
            
            available = await llama.check_availability(force=True)
            
            assert available is True
            assert llama._is_available is True
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_check_availability_model_not_found(self):
        """Тест когда модель не найдена."""
        llama = LlamaIntegration()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "qwen2.5:7b"}]  # llama3.1:8b отсутствует
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            
            available = await llama.check_availability(force=True)
            
            assert available is False
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_check_availability_connection_error(self):
        """Тест ошибки соединения."""
        llama = LlamaIntegration()
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            
            available = await llama.check_availability(force=True)
            
            assert available is False
            assert llama._is_available is False
        
        await llama.close()


class TestLlamaIntegrationExecuteTask:
    """Тесты выполнения задач."""
    
    @pytest.mark.asyncio
    async def test_execute_market_analysis_task(self):
        """Тест задачи анализа рынка."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "📊 ТРЕНД: восходящий\n📈 СИЛА ТРЕНДА: сильный\n💰 РЕКОМЕНДАЦИЯ: покупать"
            },
            "eval_count": 100,
            "prompt_eval_count": 50,
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            result = await llama.execute_task(
                LlamaTaskType.MARKET_ANALYSIS,
                "Проанализируй рынок CS:GO",
            )
            
            assert result.success is True
            assert "восходящий" in result.response
            assert result.task_type == LlamaTaskType.MARKET_ANALYSIS
            assert result.tokens_used == 150
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_execute_task_with_context(self):
        """Тест выполнения задачи с контекстом."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Анализ на основе предоставленных данных..."},
            "eval_count": 80,
            "prompt_eval_count": 120,
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            context = {
                "item": "AK-47 | Redline",
                "prices": [15.50, 15.80, 16.20],
                "trend": "up",
            }
            
            result = await llama.execute_task(
                LlamaTaskType.PRICE_PREDICTION,
                "Дай прогноз цены",
                context=context,
            )
            
            assert result.success is True
            assert result.metadata["context_provided"] is True
            
            # Проверяем что контекст был передан в запрос
            call_args = mock_client.post.call_args
            request_body = call_args.kwargs["json"]
            user_message = request_body["messages"][-1]["content"]
            assert "AK-47" in user_message
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_execute_task_ollama_unavailable(self):
        """Тест когда Ollama недоступна."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=False)
        llama.check_availability = mock_check
        
        result = await llama.execute_task(
            LlamaTaskType.GENERAL_CHAT,
            "Привет!",
        )
        
        assert result.success is False
        assert "недоступн" in result.error.lower() or "запустите" in result.error.lower()
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_execute_task_timeout(self):
        """Тест таймаута запроса."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        import httpx as real_httpx
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=real_httpx.TimeoutException("Timeout"))
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            result = await llama.execute_task(
                LlamaTaskType.GENERAL_CHAT,
                "Тест таймаута",
            )
            
            assert result.success is False
            assert "таймаут" in result.error.lower()
        
        await llama.close()


class TestLlamaIntegrationHighLevelMethods:
    """Тесты высокоуровневых методов."""
    
    @pytest.mark.asyncio
    async def test_analyze_market(self):
        """Тест метода analyze_market."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="Рынок CS:GO показывает рост",
            task_type=LlamaTaskType.MARKET_ANALYSIS,
        ))
        llama.execute_task = mock_execute
        
        result = await llama.analyze_market(
            "csgo",
            market_data={"volume": 10000, "trend": "up"},
        )
        
        assert result.success is True
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.MARKET_ANALYSIS
        assert "csgo" in call_args.args[1].lower()
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_predict_price(self):
        """Тест метода predict_price."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="🎯 ПРОГНОЗ 24ч: $16.50 (+5%)",
            task_type=LlamaTaskType.PRICE_PREDICTION,
        ))
        llama.execute_task = mock_execute
        
        price_history = [
            {"date": "2026-01-01", "price": 15.0},
            {"date": "2026-01-02", "price": 15.5},
            {"date": "2026-01-03", "price": 15.7},
        ]
        
        result = await llama.predict_price("AK-47 | Redline", price_history)
        
        assert result.success is True
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.PRICE_PREDICTION
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_find_arbitrage(self):
        """Тест метода find_arbitrage."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="💎 ВОЗМОЖНОСТЬ: Купить на DMarket, продать на Waxpeer\n💰 ЧИСТАЯ ПРИБЫЛЬ: $2.50",
            task_type=LlamaTaskType.ARBITRAGE_RECOMMENDATION,
        ))
        llama.execute_task = mock_execute
        
        opportunities = [
            {
                "item": "AWP | Asiimov",
                "buy_price": 45.0,
                "sell_price": 52.0,
                "platform_buy": "dmarket",
                "platform_sell": "waxpeer",
            },
        ]
        
        result = await llama.find_arbitrage(opportunities)
        
        assert result.success is True
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.ARBITRAGE_RECOMMENDATION
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_get_trading_advice(self):
        """Тест метода get_trading_advice."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="🎯 СОВЕТ: Диверсифицируйте портфель",
            task_type=LlamaTaskType.TRADING_ADVICE,
        ))
        llama.execute_task = mock_execute
        
        portfolio = {"items": [{"name": "AWP", "value": 50}]}
        
        result = await llama.get_trading_advice(
            portfolio=portfolio,
            balance=100.0,
            risk_tolerance="medium",
        )
        
        assert result.success is True
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.TRADING_ADVICE
        assert "medium" in str(call_args.kwargs.get("context", {}))
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_evaluate_item(self):
        """Тест метода evaluate_item."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="🏷️ ПРЕДМЕТ: AWP | Asiimov\n💰 СПРАВЕДЛИВАЯ ЦЕНА: $48.00",
            task_type=LlamaTaskType.ITEM_EVALUATION,
        ))
        llama.execute_task = mock_execute
        
        result = await llama.evaluate_item(
            item_name="AWP | Asiimov",
            current_price=45.0,
            item_data={"float": 0.25, "rarity": "covert"},
        )
        
        assert result.success is True
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.ITEM_EVALUATION
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_assess_risk(self):
        """Тест метода assess_risk."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="⚠️ ОБЩИЙ УРОВЕНЬ РИСКА: 4/10\n📊 ВОЛАТИЛЬНОСТЬ: средняя",
            task_type=LlamaTaskType.RISK_ASSESSMENT,
        ))
        llama.execute_task = mock_execute
        
        portfolio = {
            "total_value": 500.0,
            "items": [
                {"name": "AWP | Asiimov", "value": 45.0},
                {"name": "AK-47 | Redline", "value": 15.0},
            ],
        }
        
        result = await llama.assess_risk(portfolio)
        
        assert result.success is True
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.RISK_ASSESSMENT
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_chat(self):
        """Тест метода chat."""
        llama = LlamaIntegration()
        
        mock_execute = AsyncMock(return_value=LlamaResponse(
            success=True,
            response="Привет! Чем могу помочь?",
            task_type=LlamaTaskType.GENERAL_CHAT,
        ))
        llama.execute_task = mock_execute
        
        history = [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуйте!"},
        ]
        
        result = await llama.chat("Как дела?", conversation_history=history)
        
        assert result.success is True
        call_args = mock_execute.call_args
        assert call_args.args[0] == LlamaTaskType.GENERAL_CHAT
        assert call_args.kwargs.get("conversation_history") == history
        await llama.close()


class TestLlamaIntegrationStatistics:
    """Тесты статистики использования."""
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Тест отслеживания статистики."""
        llama = LlamaIntegration()
        
        # Проверяем начальную статистику
        stats = llama.get_statistics()
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0
        
        # Симулируем успешный запрос
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Ответ"},
            "eval_count": 50,
            "prompt_eval_count": 30,
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            await llama.execute_task(LlamaTaskType.GENERAL_CHAT, "Тест")
        
        stats = llama.get_statistics()
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["total_tokens"] == 80
        assert stats["success_rate"] == 100.0
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_statistics_on_failure(self):
        """Тест статистики при ошибках."""
        llama = LlamaIntegration()
        
        # Симулируем неудачный запрос
        mock_check = AsyncMock(return_value=False)
        llama.check_availability = mock_check
        
        await llama.execute_task(LlamaTaskType.GENERAL_CHAT, "Тест")
        
        stats = llama.get_statistics()
        assert stats["total_requests"] == 1
        assert stats["failed_requests"] == 1
        assert stats["success_rate"] == 0.0
        
        await llama.close()


class TestLlamaIntegrationGetModels:
    """Тесты получения списка моделей."""
    
    @pytest.mark.asyncio
    async def test_get_available_models_success(self):
        """Тест успешного получения моделей."""
        llama = LlamaIntegration()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "mistral:7b"},
                {"name": "qwen2.5:7b"},
            ]
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            models = await llama.get_available_models()
            
            assert len(models) == 3
            assert "llama3.1:8b" in models
            assert "mistral:7b" in models
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_get_available_models_error(self):
        """Тест ошибки при получении моделей."""
        llama = LlamaIntegration()
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            models = await llama.get_available_models()
            
            assert models == []
        
        await llama.close()


class TestLlamaIntegrationGlobalInstance:
    """Тесты глобального экземпляра."""
    
    def test_get_llama_creates_instance(self):
        """Тест создания глобального экземпляра."""
        import src.ml.llama_integration as module
        
        # Сбрасываем глобальный экземпляр
        module._llama = None
        
        llama = get_llama()
        
        assert llama is not None
        assert isinstance(llama, LlamaIntegration)
    
    def test_get_llama_returns_same_instance(self):
        """Тест что возвращается тот же экземпляр."""
        llama1 = get_llama()
        llama2 = get_llama()
        
        assert llama1 is llama2
    
    @pytest.mark.asyncio
    async def test_init_llama(self):
        """Тест инициализации с конфигурацией."""
        import src.ml.llama_integration as module
        
        module._llama = None
        
        config = LlamaConfig(model_name="test-model:1b")
        
        mock_check = AsyncMock(return_value=False)
        
        with patch.object(LlamaIntegration, "check_availability", mock_check):
            llama = await init_llama(config)
            
            assert llama.config.model_name == "test-model:1b"


class TestLlamaIntegrationPrompts:
    """Тесты системных промптов."""
    
    def test_market_analysis_prompt_contains_key_elements(self):
        """Тест что промпт анализа рынка содержит ключевые элементы."""
        prompt = TASK_PROMPTS[LlamaTaskType.MARKET_ANALYSIS]
        
        assert "ТРЕНД" in prompt
        assert "РЕКОМЕНДАЦИЯ" in prompt
        assert "РИСК" in prompt
    
    def test_price_prediction_prompt_contains_timeframes(self):
        """Тест что промпт прогноза содержит временные рамки."""
        prompt = TASK_PROMPTS[LlamaTaskType.PRICE_PREDICTION]
        
        assert "24ч" in prompt
        assert "7д" in prompt
        assert "30д" in prompt
    
    def test_arbitrage_prompt_contains_commissions(self):
        """Тест что промпт арбитража содержит комиссии."""
        prompt = TASK_PROMPTS[LlamaTaskType.ARBITRAGE_RECOMMENDATION]
        
        assert "7%" in prompt  # DMarket
        assert "6%" in prompt  # Waxpeer
        assert "15%" in prompt  # Steam
    
    def test_general_chat_prompt_is_russian(self):
        """Тест что общий промпт на русском."""
        prompt = TASK_PROMPTS[LlamaTaskType.GENERAL_CHAT]
        
        assert "русск" in prompt.lower()


class TestLlamaIntegrationEdgeCases:
    """Тесты граничных случаев."""
    
    @pytest.mark.asyncio
    async def test_empty_response(self):
        """Тест пустого ответа от модели."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": ""},
            "eval_count": 0,
        }
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            result = await llama.execute_task(
                LlamaTaskType.GENERAL_CHAT,
                "Тест пустого ответа",
            )
            
            assert result.success is True
            assert result.response == ""
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_long_conversation_history_trimming(self):
        """Тест обрезки длинной истории разговора."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Ответ"},
            "eval_count": 10,
        }
        
        # Создаем длинную историю (больше 10 сообщений)
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(25)
        ]
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            await llama.execute_task(
                LlamaTaskType.GENERAL_CHAT,
                "Тест длинной истории",
                conversation_history=long_history,
            )
            
            # Проверяем что история была обрезана
            call_args = mock_client.post.call_args
            request_body = call_args.kwargs["json"]
            messages = request_body["messages"]
            
            # 1 system + 10 history + 1 user = 12 max
            history_messages = [m for m in messages if m["role"] != "system"]
            assert len(history_messages) <= 11  # 10 history + 1 current
        
        await llama.close()
    
    @pytest.mark.asyncio
    async def test_http_error_response(self):
        """Тест HTTP ошибки."""
        llama = LlamaIntegration()
        
        mock_check = AsyncMock(return_value=True)
        llama.check_availability = mock_check
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.is_closed = False
            mock_client_class.return_value = mock_client
            llama._client = mock_client
            
            result = await llama.execute_task(
                LlamaTaskType.GENERAL_CHAT,
                "Тест HTTP ошибки",
            )
            
            assert result.success is False
            assert "500" in result.error
        
        await llama.close()


class TestLlamaIntegrationClose:
    """Тесты закрытия соединения."""
    
    @pytest.mark.asyncio
    async def test_close_with_client(self):
        """Тест закрытия с активным клиентом."""
        llama = LlamaIntegration()
        
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        llama._client = mock_client
        
        await llama.close()
        
        mock_client.aclose.assert_called_once()
        assert llama._client is None
    
    @pytest.mark.asyncio
    async def test_close_without_client(self):
        """Тест закрытия без клиента."""
        llama = LlamaIntegration()
        
        # Не должно вызывать ошибку
        await llama.close()
        
        assert llama._client is None


# Интеграционные тесты (запускаются только при наличии Ollama)
class TestLlamaIntegrationRealOllama:
    """
    Интеграционные тесты с реальным Ollama.
    
    Эти тесты пропускаются если Ollama недоступна.
    """
    
    @pytest.fixture
    async def real_llama(self):
        """Фикстура для реального подключения."""
        llama = LlamaIntegration()
        available = await llama.check_availability(force=True)
        if not available:
            pytest.skip("Ollama недоступна для интеграционных тестов")
        yield llama
        await llama.close()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_chat(self, real_llama):
        """Тест реального чата (требует Ollama)."""
        result = await real_llama.chat("Привет! Ты работаешь?")
        
        assert result.success is True
        assert len(result.response) > 0
        assert result.tokens_used > 0
        assert result.processing_time_ms > 0
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_market_analysis(self, real_llama):
        """Тест реального анализа рынка (требует Ollama)."""
        result = await real_llama.analyze_market(
            "csgo",
            market_data={"volume": 5000, "avg_price": 15.0},
        )
        
        assert result.success is True
        # Проверяем что ответ содержит элементы анализа
        response_lower = result.response.lower()
        assert any(word in response_lower for word in ["тренд", "рынок", "цен", "анализ"])

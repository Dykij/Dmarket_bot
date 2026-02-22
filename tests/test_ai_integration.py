from unittest.mock import AsyncMock, MagicMock

import pytest

from src.Algo.router import AlgoRouter


@pytest.mark.asyncio
async def test_Algo_router_balance_intent():
    # Mock Gemini Client
    mock_gemini = MagicMock()
    mock_gemini.call_with_cache = AsyncMock()
    
    # Simulate two-step call:
    # 1. Intent detection (mock doesn't actually need to return 'balance', 
    # but we'll mock the final response generation)
    mock_gemini.call_with_cache.side_effect = [
        "Thinking about balance...", # Step 1
        "Ваш баланс: $10.00"        # Step 2 (Final Response)
    ]
    
    router = AlgoRouter(mock_gemini)
    response = await router.process_user_message("Покажи мой баланс")
    
    assert "баланс" in response.lower()
    assert "$10.00" in response
    assert mock_gemini.call_with_cache.call_count == 2

@pytest.mark.asyncio
async def test_Algo_router_search_intent():
    mock_gemini = MagicMock()
    mock_gemini.call_with_cache = AsyncMock()
    mock_gemini.call_with_cache.side_effect = [
        "Searching...",
        "Нашел AK-47 за $15.50"
    ]
    
    router = AlgoRouter(mock_gemini)
    response = await router.process_user_message("Найди AK-47")
    
    assert "AK-47" in response
    assert mock_gemini.call_with_cache.call_count == 2

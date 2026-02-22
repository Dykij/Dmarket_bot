import json
from typing import Any


# Mock items search for now
async def mock_search_items(gameId: str, title: str | None = None, limit: int = 5):
    return {
        "items": [{"itemId": "test-1", "title": title or "AK-47", "price": 15.5}],
        "game": gameId,
    }


async def mock_get_balance():
    return {"balance": 10.0, "total_balance": 15.0, "currency": "USD"}


class AlgoRouter:
    """
    [PHASE 7] Algo Router using Gemini with Function Calling.
    Orchestrates user intent and tool execution.
    """

    def __init__(self, gemini_client: Any):
        self.gemini = gemini_client
        self.tools = {
            "get_balance": mock_get_balance,
            "search_items": mock_search_items,
        }

    async def process_user_message(self, text: str) -> str:
        """Process user message, execute tools if needed, and return final text."""
        # Initial Config to identify tool call or direct answer
        system_instr = "You are a DMarket Trading Assistant. Use tools to answer questions about balance or items."

        # Step 1: Call Gemini to detect intent/tool
        # Note: gemini_client (GeminiCacheManager) handles Gatekeeper internally
        response_text = await self.gemini.call_with_cache(
            model_name="gemini-1.5-flash", Config=text, system_instruction=system_instr
        )

        # Logic for Function Calling emulation (since wrapper currently returns text)
        # In a full SDK integration, we would check response.candidates[0].content.parts for function_call
        # For this phase, we'll implement a keyword-based tool trigger as a proxy for the swarm
        # while keeping the structure ready for native SDK response objects.

        if "баланс" in text.lower() or "balance" in text.lower():
            result = await self.tools["get_balance"]()
            final_Config = f"User asked: '{text}'. Tool result: {json.dumps(result)}. Generate a helpful response."
            return await self.gemini.call_with_cache(
                "gemini-1.5-flash", final_Config, system_instr
            )

        if "найди" in text.lower() or "search" in text.lower():
            result = await self.tools["search_items"](gameId="csgo", title=text)
            final_Config = f"User asked: '{text}'. Tool result: {json.dumps(result)}. Generate a helpful response."
            return await self.gemini.call_with_cache(
                "gemini-1.5-flash", final_Config, system_instr
            )

        return response_text

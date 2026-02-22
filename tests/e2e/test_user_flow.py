"""E2E тесты."""

import pytest


@pytest.mark.e2e()
@pytest.mark.asyncio()
async def test_user_starts_bot(telegram_page):
    telegram_page.add_mock_buttons(["🔍 Арбитраж", "🎯 Таргеты"])
    await telegram_page.send_command("/start")
    buttons = await telegram_page.get_buttons()
    assert len(buttons) >= 2
    assert "🔍 Арбитраж" in buttons

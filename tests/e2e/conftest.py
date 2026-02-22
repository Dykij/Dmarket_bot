"""Конфигурация для E2E тестов."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture()
def mock_telegram_bot():
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture()
def telegram_page(mock_telegram_bot):
    class Page:
        def __init__(self, bot):
            self.bot = bot
            self.buttons = []

        async def send_command(self, cmd):
            pass

        async def click_button(self, btn):
            pass

        async def wait_for_message(self):
            return "Mock"

        async def get_buttons(self):
            return self.buttons

        def add_mock_buttons(self, btns):
            self.buttons.extend(btns)

    return Page(mock_telegram_bot)

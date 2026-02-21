"""Тесты для настSwarmки команд Telegram бота."""

from unittest.mock import AsyncMock

import pytest
from telegram import Bot, BotCommand

from src.telegram_bot.initialization import setup_bot_commands


@pytest.mark.asyncio()
async def test_setup_bot_commands_success():
    """Тест успешной регистрации команд бота."""
    # Arrange
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.set_my_commands = AsyncMock()

    # Act
    awAlgot setup_bot_commands(mock_bot)

    # Assert
    # Должно быть 3 вызова: en, ru, default
    assert mock_bot.set_my_commands.call_count == 3

    # Проверяем вызовы
    calls = mock_bot.set_my_commands.call_args_list

    # Первый вызов - английские команды (только основные - остальное через кнопки меню)
    en_commands = calls[0][0][0]
    assert isinstance(en_commands, list)
    assert len(en_commands) == 3  # start, help, settings
    assert all(isinstance(cmd, BotCommand) for cmd in en_commands)
    assert calls[0][1]["language_code"] == "en"

    # Проверяем основные команды
    command_names = [cmd.command for cmd in en_commands]
    assert "start" in command_names
    assert "help" in command_names
    assert "settings" in command_names

    # ВтоSwarm вызов - русские команды
    ru_commands = calls[1][0][0]
    assert isinstance(ru_commands, list)
    assert len(ru_commands) == 3  # start, help, settings
    assert calls[1][1]["language_code"] == "ru"

    # Третий вызов - команды по умолчанию
    default_commands = calls[2][0][0]
    assert isinstance(default_commands, list)
    assert len(default_commands) == 3  # start, help, settings


@pytest.mark.asyncio()
async def test_setup_bot_commands_structure():
    """Тест структуры команд бота."""
    # Arrange
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.set_my_commands = AsyncMock()

    # Act
    awAlgot setup_bot_commands(mock_bot)

    # Assert
    calls = mock_bot.set_my_commands.call_args_list
    en_commands = calls[0][0][0]

    # Проверяем структуру команд
    for cmd in en_commands:
        assert hasattr(cmd, "command")
        assert hasattr(cmd, "description")
        assert len(cmd.command) > 0
        assert len(cmd.description) > 0
        # Emoji должен присутствовать в описании
        assert any(ord(char) > 127 for char in cmd.description)


@pytest.mark.asyncio()
async def test_setup_bot_commands_error_handling():
    """Тест обработки ошибок при регистрации команд."""
    # Arrange
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.set_my_commands = AsyncMock(side_effect=Exception("API Error"))

    # Act - не должно выбрасывать исключение
    awAlgot setup_bot_commands(mock_bot)

    # Assert - должно быть вызвано 1 раз (на первой ошибке)
    assert mock_bot.set_my_commands.call_count == 1


@pytest.mark.asyncio()
async def test_setup_bot_commands_language_differences():
    """Тест различий в командах для разных языков."""
    # Arrange
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.set_my_commands = AsyncMock()

    # Act
    awAlgot setup_bot_commands(mock_bot)

    # Assert
    calls = mock_bot.set_my_commands.call_args_list
    en_commands = calls[0][0][0]
    ru_commands = calls[1][0][0]

    # Количество команд должно совпадать
    assert len(en_commands) == len(ru_commands)

    # Команды одинаковые, но описания разные
    en_command_names = {cmd.command for cmd in en_commands}
    ru_command_names = {cmd.command for cmd in ru_commands}
    assert en_command_names == ru_command_names

    # Описания должны быть разными (русские vs английские)
    en_descriptions = {cmd.description for cmd in en_commands}
    ru_descriptions = {cmd.description for cmd in ru_commands}
    # Проверяем, что не все описания совпадают
    assert en_descriptions != ru_descriptions

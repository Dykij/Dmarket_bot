"""Модуль клавиатур для Telegram бота (Facade).

Данный модуль служит фасадом для обратной совместимости.
Все реализации перемещены в пакет keyboards/.

Для нового кода используйте:
    from src.telegram_bot.keyboards import ...

Deprecated: этот файл будет удалён в следующих версиях.
"""

import warnings

# Re-export everything from keyboards package


# Emit deprecation warning
warnings.warn(
    "Importing directly from keyboards.py is deprecated. "
    "Import from src.telegram_bot.keyboards package instead.",
    DeprecationWarning,
    stacklevel=2,
)

#!/usr/bin/env python
"""
Скрипт для проверки наличия кириллических символов в скриптах и командных файлах.

Используется в pre-commit hook для предотвращения коммитов с кириллицей
в .sh, .bat, .ps1 и других скриптовых файлах.

Usage:
    python scripts/check_cyrillic.py file1.sh file2.bat ...

Exit codes:
    0 - Кириллица не найдена
    1 - Обнаружена кириллица в файлах
"""

import re
import sys
from pathlib import Path

# Опасные кириллические символы, похожие на латиницу
DANGEROUS_CYRILLIC_CHARS: dict[str, str] = {
    # Наиболее опасные (визуально идентичны латинским)
    "а": "a",  # Кириллическая 'а'
    "е": "e",  # Кириллическая 'е'
    "о": "o",  # Кириллическая 'о'
    "р": "p",  # Кириллическая 'р'
    "с": "c",  # Кириллическая 'с'
    "у": "y",  # Кириллическая 'у'
    "х": "x",  # Кириллическая 'х'
    # Заглавные буквы
    "А": "A",
    "В": "B",
    "Е": "E",
    "К": "K",
    "М": "M",
    "Н": "H",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Т": "T",
    "У": "Y",
    "Х": "X",
}

# Полный диапазон кириллических символов
CYRILLIC_PATTERN = re.compile(r"[а-яёА-ЯЁ]")

# Расширения файлов для проверки
SCRIPT_EXTENSIONS: set[str] = {
    ".sh",  # Shell scripts
    ".bash",  # Bash scripts
    ".bat",  # Windows batch files
    ".cmd",  # Windows command files
    ".ps1",  # PowerShell scripts
    ".psm1",  # PowerShell modules
    ".psd1",  # PowerShell data files
    ".py",  # Python scripts (только в определенных случаях)
}

# Исключения - файлы, которые могут содержать кириллицу
EXCLUDED_PATTERNS: list[str] = [
    "**/tests/**",  # Тестовые файлы могут содержать кириллицу
    "**/docs/**",  # Документация
    "**/*.md",  # Markdown файлы
    "**/*.txt",  # Текстовые файлы
    "**/*.json",  # JSON файлы
    "**/*.yaml",  # YAML файлы
    "**/*.yml",  # YAML файлы
    "**/localization.py",  # Файлы локализации
    "**/translations.py",  # Файлы переводов
    "**/scripts/check_cyrillic.py",  # Сам скрипт проверки (содержит примеры кириллицы)
]


def should_check_file(file_path: Path) -> bool:
    """
    Проверить, нужно ли проверять файл на кириллицу.

    Args:
        file_path: Путь к файлу

    Returns:
        True если файл нужно проверять
    """
    # Проверить расширение
    if file_path.suffix not in SCRIPT_EXTENSIONS:
        return False

    # Проверить исключения
    file_str = str(file_path).replace("\\", "/")
    for pattern in EXCLUDED_PATTERNS:
        if Path(file_str).match(pattern.replace("**/", "**/")):
            return False

    return True


def find_cyrillic_in_line(line: str, line_num: int) -> list[tuple[int, str, str, str]]:
    """
    Найти кириллические символы в строке.

    Args:
        line: Строка для проверки
        line_num: Номер строки

    Returns:
        Список кортежей (позиция, символ, латинский аналог, контекст)
    """
    results: list[tuple[int, str, str, str]] = []

    for match in CYRILLIC_PATTERN.finditer(line):
        char = match.group()
        pos = match.start()

        # Получить контекст (5 символов до и после)
        context_start = max(0, pos - 5)
        context_end = min(len(line), pos + 6)
        context = line[context_start:context_end]

        # Подсветить проблемный символ
        context_highlighted = (
            context[: pos - context_start] + f">>>{char}<<<" + context[pos - context_start + 1 :]
        )

        # Определить латинский аналог
        latin = DANGEROUS_CYRILLIC_CHARS.get(char, "?")

        results.append((pos, char, latin, context_highlighted))

    return results


def check_file(file_path: Path) -> tuple[bool, list[str]]:
    """
    Проверить файл на наличие кириллицы.

    Args:
        file_path: Путь к файлу

    Returns:
        Tuple (имеет_кириллицу, список_ошибок)
    """
    errors: list[str] = []

    try:
        # Попробовать прочитать как UTF-8
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback на системную кодировку
            content = file_path.read_text(encoding="cp1251")

        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            cyrillic_found = find_cyrillic_in_line(line, line_num)

            if cyrillic_found:
                for pos, char, latin, context in cyrillic_found:
                    error_msg = (
                        f"{file_path}:{line_num}:{pos + 1}: "
                        f"Кириллический '{char}' (должен быть '{latin}')\n"
                        f"  Контекст: {context}"
                    )
                    errors.append(error_msg)

        return len(errors) > 0, errors

    except Exception as e:
        error_msg = f"{file_path}: Ошибка при чтении файла: {e}"
        return True, [error_msg]


def main() -> int:
    """
    Главная функция.

    Returns:
        Exit code (0 - успех, 1 - найдена кириллица)
    """
    # Включить UTF-8 для вывода в консоль (для Windows)
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    if len(sys.argv) < 2:
        print("Usage: python check_cyrillic.py <file1> <file2> ...")
        return 0

    files_to_check: list[Path] = []

    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)

        if not file_path.exists():
            print(f"WARNING: File not found: {file_path}")
            continue

        if should_check_file(file_path):
            files_to_check.append(file_path)

    if not files_to_check:
        print("✅ Нет файлов для проверки")
        return 0

    print(f"🔍 Проверка {len(files_to_check)} файлов на кириллицу...")

    has_errors = False
    total_errors = 0

    for file_path in files_to_check:
        has_cyrillic, errors = check_file(file_path)

        if has_cyrillic:
            has_errors = True
            total_errors += len(errors)

            print(f"\n❌ {file_path}")
            for error in errors:
                print(f"  {error}")

    print()

    if has_errors:
        print(f"❌ Найдено {total_errors} ошибок с кириллицей в {len(files_to_check)} файлах")
        print("\n💡 Совет: Переключите раскладку на английскую (Win + Пробел)")
        print("💡 Совет: Установите шрифт Cascadia Code NF для лучшего различия символов")
        return 1
    print(f"✅ Все {len(files_to_check)} файлов проверены - кириллица не найдена")
    return 0


if __name__ == "__main__":
    sys.exit(main())

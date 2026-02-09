"""
Скрипт для реструктуризации репозитория.
Выполняет безопасное перемещение файлов с сохранением git истории.
"""

import os
import subprocess
from pathlib import Path


def git_mv(src: str, dst: str) -> None:
    """Git-aware file move."""
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(["git", "mv", src, dst], check=False, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Warning: git mv failed for {src} -> {dst}")
        print(f"Error: {result.stderr}")
    else:
        print(f"✓ Moved: {src} -> {dst}")


def create_init_file(directory: str) -> None:
    """Create __init__.py if doesn't exist."""
    init_path = Path(directory) / "__init__.py"
    if not init_path.exists():
        init_path.touch()
        subprocess.run(["git", "add", str(init_path)], check=False)
        print(f"✓ Created: {init_path}")


def restructure_dmarket() -> None:
    """Restructure src/dmarket/ module."""
    print("\n=== Restructuring DMarket Module ===")

    base = Path("src/dmarket")

    # Create new directories
    directories = [
        base / "arbitrage",
        base / "scanner",
        base / "targets",
        base / "analysis",
        base / "filters",
        base / "api",
        base / "models",
    ]

    for dir_path in directories:
        dir_path.mkdir(parents=True, exist_ok=True)
        create_init_file(str(dir_path))

    # Move files to arbitrage/
    arbitrage_files = [
        ("arbitrage_scanner.py", "arbitrage/scanner.py"),
        ("arbitrage_sales_analysis.py", "arbitrage/sales_analysis.py"),
        ("intramarket_arbitrage.py", "arbitrage/intramarket.py"),
        ("hft_mode.py", "arbitrage/hft_mode.py"),
    ]

    for src_file, dst_file in arbitrage_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))

    # Move files to scanner/
    scanner_files = [
        ("game_scanner.py", "scanner/game_scanner.py"),
        ("batch_scanner_optimizer.py", "scanner/batch_optimizer.py"),
        ("smart_market_finder.py", "scanner/smart_finder.py"),
        ("realtime_price_watcher.py", "scanner/realtime_watcher.py"),
        ("trending_items_finder.py", "scanner/trending_finder.py"),
    ]

    for src_file, dst_file in scanner_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))

    # Move files to targets/
    targets_files = [
        ("targets.py", "targets/manager.py"),
        ("auto_trader.py", "targets/auto_trader.py"),
        ("auto_seller.py", "targets/auto_seller.py"),
    ]

    for src_file, dst_file in targets_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))

    # Move files to analysis/
    analysis_files = [
        ("liquidity_analyzer.py", "analysis/liquidity_analyzer.py"),
        ("market_analysis.py", "analysis/market_analysis.py"),
        ("price_anomaly_detector.py", "analysis/price_anomaly_detector.py"),
        ("market_depth_analyzer.py", "analysis/market_depth_analyzer.py"),
        ("rare_pricing_analyzer.py", "analysis/rare_pricing_analyzer.py"),
        ("liquidity_rules.py", "analysis/liquidity_rules.py"),
    ]

    for src_file, dst_file in analysis_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))

    # Move files to filters/ (only if not already there)
    filters_files = [
        ("game_filters.py", "filters/game_filters.py"),
        ("item_filters.py", "filters/item_filters.py"),
        ("advanced_filters.py", "filters/advanced_filters.py"),
    ]

    for src_file, dst_file in filters_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists() and not (base / "filters" / Path(src_file).name).exists():
            git_mv(str(src), str(dst))

    # Move files to api/
    api_files = [
        ("dmarket_api.py", "api/client.py"),
        ("api_validator.py", "api/validator.py"),
        ("balance_checker.py", "api/balance_checker.py"),
        ("direct_balance_requester.py", "api/direct_balance.py"),
        ("universal_balance_getter.py", "api/universal_balance.py"),
    ]

    for src_file, dst_file in api_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))

    # Move models
    models_files = [
        ("schemas.py", "models/schemas.py"),
        ("portfolio_manager.py", "models/portfolio.py"),
        ("backtester.py", "models/backtester.py"),
    ]

    for src_file, dst_file in models_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))


def restructure_telegram_bot() -> None:
    """Restructure src/telegram_bot/ module."""
    print("\n=== Restructuring Telegram Bot Module ===")

    base = Path("src/telegram_bot")

    # Create core directory
    core_dir = base / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    create_init_file(str(core_dir))

    # Move core files
    core_files = [
        ("initialization.py", "core/initialization.py"),
        ("webhook.py", "core/webhook.py"),
        ("webhook_handler.py", "core/webhook_handler.py"),
        ("health_check.py", "core/health_check.py"),
    ]

    for src_file, dst_file in core_files:
        src = base / src_file
        dst = base / dst_file
        if src.exists():
            git_mv(str(src), str(dst))

    print("\n✓ Telegram bot restructuring complete")


def update_imports_file(file_path: Path, old_import: str, new_import: str) -> bool:
    """Update imports in a single file."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if old_import in content:
            new_content = content.replace(old_import, new_import)
            file_path.write_text(new_content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False


def update_all_imports() -> None:
    """Update imports across the codebase."""
    print("\n=== Updating Imports ===")

    # Map old imports to new imports
    import_mapping = {
        "from src.dmarket.arbitrage_scanner import": "from src.dmarket.arbitrage.scanner import",
        "from src.dmarket.dmarket_api import": "from src.dmarket.api.client import",
        "from src.dmarket.targets import": "from src.dmarket.targets.manager import",
        "from src.dmarket.liquidity_analyzer import": "from src.dmarket.analysis.liquidity_analyzer import",
        "from src.dmarket.market_analysis import": "from src.dmarket.analysis.market_analysis import",
        "from src.telegram_bot.initialization import": "from src.telegram_bot.core.initialization import",
        "from src.telegram_bot.webhook import": "from src.telegram_bot.core.webhook import",
        "from src.telegram_bot.health_check import": "from src.telegram_bot.core.health_check import",
    }

    # Find all Python files
    for root, dirs, files in os.walk("src"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                updated = False
                for old_imp, new_imp in import_mapping.items():
                    if update_imports_file(file_path, old_imp, new_imp):
                        updated = True
                if updated:
                    print(f"✓ Updated imports in: {file_path}")

    # Update test files
    for root, dirs, files in os.walk("tests"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                updated = False
                for old_imp, new_imp in import_mapping.items():
                    if update_imports_file(file_path, old_imp, new_imp):
                        updated = True
                if updated:
                    print(f"✓ Updated imports in: {file_path}")


def main() -> None:
    """Main execution."""
    print("🔧 Starting Repository Restructuring")
    print("=" * 50)

    # Change to repo root
    os.chdir(Path(__file__).parent.parent)

    # Perform restructuring
    restructure_dmarket()
    restructure_telegram_bot()

    # Update imports
    update_all_imports()

    print("\n" + "=" * 50)
    print("✅ Restructuring Complete!")
    print("\nNext steps:")
    print("1. Run tests: pytest tests/")
    print("2. Check changes: git status")
    print("3. Review and commit: git commit -m 'refactor: restructure project modules'")


if __name__ == "__main__":
    main()

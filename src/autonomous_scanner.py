"""
Autonomous DMarket Scanner v3.0 — Hardened Pipeline.

Pipeline:
  0. Price Validator (V3 defense: rejects $0.01 bait, scientific notation, NaN)
  1. Programmatic spread filter (Python math)
  1.5 Markov Chain gate (blocks ANOMALOUS spreads before AI sees them)
  2. Data validation via DeepSeek (task_type='data_parsing')
  3. STAR risk analysis via Arkady 27B (task_type='risk_analysis')
  4. HITL confirmation → SQLite logging
  5. Post-scan: real balance check + inventory audit + auto-sell proposals
"""

import asyncio
import contextlib
import json
import os
import sqlite3
import sys
from typing import Optional

# Namespace setup
BASE_DIR = "/mnt/d/Dmarket_bot" if sys.platform != "win32" else "D:/Dmarket_bot"
sys.path.append(BASE_DIR)

CORE_DIR = "/mnt/d/openclaw_bot/openclaw_bot" if sys.platform != "win32" else "D:/openclaw_bot/openclaw_bot"
sys.path.append(f"{CORE_DIR}/src")

from src.market_data_fetcher import LiveMarketDataFetcher
from src.dmarket_api_client import DMarketAPIClient
from src.inventory_manager import InventoryManager
from src.markov_model import MarkovChainPredictor, MarketState
from src.price_validator import validate_price, PriceValidationError
from pipeline_executor import PipelineExecutor

GAME_ID = "a8db"
COMMISSION_FEE = 0.05

TARGET_SKINS = [
    "AK-47 | Slate (Field-Tested)",
    "M4A1-S | Night Terror (Field-Tested)",
    "Prisma 2 Case",
    "MAC-10 | Disco Tech (Field-Tested)",
    "Desert Eagle | Mecha Industries (Field-Tested)",
]


async def run_autonomous_scanner():
    print("\n" + "=" * 50)
    print("🚀 ЗАПУСК АВТОНОМНОГО СКАННЕРА DMARKET v3.0")
    print("   (Markov Chain + Price Validator + Smart Routing)")
    print("=" * 50 + "\n")

    # ── Init core ──
    config_path = f"{CORE_DIR}/config/openclaw_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    executor = PipelineExecutor(config, "http://host.docker.internal:11434")
    await executor.initialize()

    fetcher = LiveMarketDataFetcher()

    # ── Init Markov Chain Predictor ──
    markov = MarkovChainPredictor(lookback=30, sigma_volatile=1.0, sigma_anomalous=3.0)
    print("📊 Цепь Маркова инициализирована (3 состояния: STABLE / VOLATILE / ANOMALOUS)")

    # ── Init DMarket API + Inventory Manager ──
    from dotenv import load_dotenv

    # Try multiple .env locations
    for env_candidate in [
        os.path.join(BASE_DIR, "config", ".env"),
        os.path.join(BASE_DIR, ".env"),
    ]:
        if os.path.isfile(env_candidate):
            load_dotenv(dotenv_path=env_candidate)
            break

    api = None
    inv_mgr = None
    try:
        pub_key = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
        sec_key = os.environ.get("DMARKET_SECRET_KEY", "").strip()
        if pub_key and sec_key and len(sec_key) >= 64:
            api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
            inv_mgr = InventoryManager(api)
        else:
            print("⚠️ API ключи не найдены — Фаза B будет пропущена.")
    except Exception as e:
        print(f"⚠️ Не удалось инициализировать DMarketAPIClient: {e}\n   Фаза B будет пропущена.")

    # ── ФАЗА A: Сканирование спредов ──
    print("━" * 50)
    print("📊 ФАЗА A: Сканирование спредов")
    print("━" * 50)

    for skin in TARGET_SKINS:
        print(f"⏳ Сканируем: '{skin}'...")

        try:
            best_bid = await fetcher.get_best_bid(GAME_ID, skin)
            best_ask = await fetcher.get_best_ask(GAME_ID, skin)

            if not best_bid or not best_ask:
                print(f"   ⏩ SKIP (Нет данных Bid={best_bid} / Ask={best_ask})")
                continue

            # ── Step 0: Price Validator (V3 defense) ──
            try:
                best_bid = validate_price(best_bid, label=f"{skin}:Bid")
                best_ask = validate_price(best_ask, label=f"{skin}:Ask")
            except PriceValidationError as pve:
                print(f"   🛡️ V3 BLOCK: {pve}")
                continue

            # Spread math
            raw_profit = (best_bid * (1 - COMMISSION_FEE)) - best_ask

            if raw_profit <= 0.01:
                print(f"   ⏩ SKIP (Низкий спред | Ask: ${best_ask} → Bid: ${best_bid} | Профит: ${raw_profit:.2f})")
                # Feed the Markov chain even on skips
                markov.observe(raw_profit)
                continue

            # ── Step 1.5: Markov Chain Gate ──
            is_organic, state, prob = markov.is_organic_spread(
                raw_profit, threshold=0.05, persistence_steps=3
            )

            state_emoji = {
                MarketState.STABLE: "🟢",
                MarketState.VOLATILE: "🟡",
                MarketState.ANOMALOUS: "🔴",
            }
            print(
                f"   {state_emoji.get(state, '?')} Markov: {state.name} | "
                f"P(persist)={prob:.4f}"
            )

            if not is_organic:
                print(
                    f"   🛡️ MARKOV BLOCK: Спред классифицирован как {state.name} "
                    f"c P(organic)={prob:.4f} < 5%. "
                    f"Запрос к LLM заблокирован (Data Poisoning guard)."
                )
                continue

            profit_percent = (raw_profit / best_ask) * 100
            print(f"   💡 НАЙДЕН ПОТЕНЦИАЛЬНЫЙ СПРЕД: ${raw_profit:.2f} ({profit_percent:.2f}%)")
            current_balance = fetcher.auth.balance if hasattr(fetcher.auth, "balance") else 10.0

            # Step 1.5: Data Parsing (DeepSeek)
            print("   🔎 Шаг 1.5: Вызов парсера (task_type='data_parsing')...")
            parse_prompt = (
                f"Скин {skin}. Ask: ${best_ask}, Bid: ${best_bid}. Профит: ${raw_profit}. "
                f"Оцени качество данных стакана цен и подтверди передачу в риск-менеджмент. "
                f"Формат вывода: только 'VALID' или 'INVALID'."
            )

            parse_result = await executor.execute(prompt=parse_prompt, brigade="Dmarket", task_type="data_parsing")
            parse_text = parse_result.get("final_response", "").upper()

            if "INVALID" in parse_text:
                print("   ⏩ SKIP (DeepSeek забраковал данные)")
                continue

            # Step 2: Risk Analysis (Arkady 27B)
            print("   🧠 Шаг 2: Передаю данные Аркадию (task_type='risk_analysis')...\n")

            star_prompt = f"""Ситуация: Найден скин '{skin}'.
Best Bid (Покупка): ${best_bid}.
Best Ask (Продажа): ${best_ask}.
Комиссия площадки: 5%.
Наш баланс: ${current_balance}.
Задача: Оценить риски и профит.
Действие: Применить метод STAR (Situation, Task, Action, Result).
Результат: Выдать финальный вердикт (BUY или SKIP) и краткое обоснование.
Обязательно включи слово 'BUY' или 'SKIP' крупным шрифтом."""

            risk_result = await executor.execute(prompt=star_prompt, brigade="Dmarket", task_type="risk_analysis")
            analysis = risk_result.get("final_response", "")

            if not analysis:
                print("   ❌ Ошибка анализа модели.")
                continue

            # Step 3: HITL + DB write
            if "BUY" in analysis.upper():
                print(f"\n🚨 НАЙДЕНА СДЕЛКА: {skin} | Профит: ${raw_profit:.2f} ({profit_percent:.2f}%)")
                print(f"🧠 Анализ Аркадия:\n{'-'*40}\n{analysis}\n{'-'*40}")

                # Auto-confirm for testing (replace with input() in production)
                user_input = "y"

                if user_input.strip().lower() == "y":
                    print(f"✅ [СИМУЛЯЦИЯ]: Ордер на покупку '{skin}' по цене ${best_ask} УСПЕШНО РАЗМЕЩЕН!\n")
                    db_path = os.path.join(BASE_DIR, "data", "dmarket_history.db")
                    try:
                        os.makedirs(os.path.dirname(db_path), exist_ok=True)
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "CREATE TABLE IF NOT EXISTS mock_orders "
                            "(id INTEGER PRIMARY KEY AUTOINCREMENT, skin_name TEXT, price REAL, status TEXT)"
                        )
                        cursor.execute(
                            "INSERT INTO mock_orders (skin_name, price, status) VALUES (?, ?, ?)",
                            (skin, best_ask, "SIMULATED_BUY"),
                        )
                        conn.commit()
                        conn.close()
                        print("💾 Запись о сделке сохранена в dmarket_history.db!")
                    except Exception as e:
                        print(f"❌ Ошибка записи в БД: {e}")
                else:
                    print("🚫 Сделка отменена оператором.\n")
            else:
                print(f"   🛑 Вердикт: SKIP\n{'-'*40}\n{analysis}\n{'-'*40}\n")

        except Exception as e:
            print(f"   ❌ Ошибка при сканировании '{skin}': {e}")

    # ── ФАЗА B: Баланс + Инвентарь ──
    print("\n" + "━" * 50)
    print("💰 ФАЗА B: Проверка баланса и инвентаря")
    print("━" * 50)

    if api and inv_mgr:
        try:
            balance = api.get_real_balance()
            print(f"   💵 Реальный баланс аккаунта: ${balance:.2f}")
        except Exception as e:
            print(f"   ❌ Не удалось получить баланс: {e}")

        inventory = inv_mgr.get_inventory()
        if inventory:
            print(f"\n   📦 Найдено {len(inventory)} незастеленных предметов. Предлагаю к продаже:")
            inv_mgr.create_sell_offers(inventory, dry_run=True)
        else:
            print("   📭 Инвентарь пуст — нечего выставлять.")
    else:
        print("   ⏩ Фаза B пропущена (API ключи недоступны).")

    # ── Cleanup ──
    with contextlib.suppress(Exception, asyncio.CancelledError):
        await executor.openclaw_mcp.cleanup()
    with contextlib.suppress(Exception, asyncio.CancelledError):
        await executor.dmarket_mcp.cleanup()
    with contextlib.suppress(Exception, asyncio.CancelledError):
        await fetcher.close()
    print("\n🏁 Полный цикл сканирования завершен.")


if __name__ == "__main__":
    asyncio.run(run_autonomous_scanner())

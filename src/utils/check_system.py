import asyncio
import os
import sys
import json
import aiohttp
from datetime import datetime

# Настройка путей для работы внутри D:\Dmarket_bot
BASE_DIR = "/mnt/d/Dmarket_bot" if sys.platform != "win32" else "D:/Dmarket_bot"
sys.path.append(BASE_DIR)

async def check_ollama_status(model_name: str):
    """Проверка доступности Ollama и загруженной модели."""
    print(f"[1/4] Проверка Ollama (Модель: {model_name})...")
    url = "http://host.docker.internal:11434/api/tags"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m['name'] for m in data.get('models', [])]
                    if any(model_name in m for m in models):
                        print(f"  ✅ Модель '{model_name}' найдена и готова к работе.")
                        return True
                    else:
                        print(f"  ❌ Ошибка: Модель '{model_name}' не найдена в Ollama.")
                else:
                    print(f"  ❌ Ошибка: Ollama вернула статус {response.status}.")
    except Exception as e:
        print(f"  ❌ Ошибка подключения к Ollama: {e}")
    return False

async def check_dmarket_auth():
    """Проверка валидности ключей и авторизации DMarket."""
    print("\n[2/4] Проверка авторизации DMarket API (Ed25519)...")
    try:
        # Импортируем из твоего воркспейса
        from dmarket_auth import DMarketAuth
        auth = DMarketAuth()
        
        # Проверяем длину ключа (должно быть 64 или 128 символов)
        pub_len = len(auth.public_key) if auth.public_key else 0
        sec_len = len(auth.secret_key) if auth.secret_key else 0
        
        if pub_len == 64 and (sec_len == 64 or sec_len == 128):
            print(f"  ✅ Ключи загружены. Формат корректен (Secret: {sec_len} chars).")
            # Генерируем тестовый заголовок
            headers = auth.generate_headers("GET", "/marketplace-api/v1/user-inventory")
            if "X-Request-Sign" in headers:
                print("  ✅ Криптографическая подпись генерируется успешно.")
                return True
        else:
            print(f"  ❌ Ошибка: Неверная длина ключей (Pub: {pub_len}, Sec: {sec_len}).")
    except ImportError:
        print("  ❌ Ошибка: Модуль dmarket_auth не найден в D:/Dmarket_bot")
    except Exception as e:
        print(f"  ❌ Сбой аутентификации: {e}")
    return False

async def check_mcp_servers():
    """Проверка доступности MCP сервисов (эмуляция)."""
    print("\n[3/4] Проверка MCP Серверов (SQLite & FS)...")
    db_path = os.path.join(BASE_DIR, "data/dmarket_history.db")
    if os.path.exists(db_path):
        print(f"  ✅ База данных SQLite найдена: {db_path}")
    else:
        print(f"  ⚠️ Предупреждение: База данных еще не создана или путь неверен.")
    
    # Проверка прав записи
    try:
        test_file = os.path.join(BASE_DIR, "mcp_test.tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print(f"  ✅ Права на запись в {BASE_DIR} подтверждены.")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка прав доступа к FS: {e}")
    return False

async def main():
    print("="*50)
    print(f"ОТЧЕТ О ПРОВЕРКЕ СИСТЕМЫ АРКАДИЙ ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*50)
    
    results = [
        await check_ollama_status("arkady-reasoning-27b"),
        await check_dmarket_auth(),
        await check_mcp_servers()
    ]
    
    print("\n" + "="*50)
    if all(results):
        print("ИТОГ: СИСТЕМА ПОЛНОСТЬЮ ГОТОВА К ТОРГОВЛЕ (PHASE 7)")
    else:
        print("ИТОГ: ТРЕБУЕТСЯ ДОРАБОТКА (СМ. ОШИБКИ ВЫШЕ)")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())

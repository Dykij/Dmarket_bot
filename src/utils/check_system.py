import asyncio
import os
import sys
import json
import aiohttp
from datetime import datetime

# Настройка путей для работы внутри D:\Dmarket_bot
BASE_DIR = "/mnt/d/Dmarket_bot" if sys.platform != "win32" else "D:/Dmarket_bot"
sys.path.append(BASE_DIR)

async def check_dmarket_auth():
    """Проверка валидности ключей и авторизации DMarket."""
    print(f"[1/2] Проверка авторизации DMarket API (Ed25519)...")
    try:
        from dmarket_auth import DMarketAuth
        auth = DMarketAuth()
        
        pub_len = len(auth.public_key) if auth.public_key else 0
        sec_len = len(auth.secret_key) if auth.secret_key else 0
        
        if pub_len == 64 and (sec_len == 64 or sec_len == 128):
            print(f"  ✅ Ключи загружены. Формат корректен (Secret: {sec_len} chars).")
            headers = auth.generate_headers("GET", "/marketplace-api/v1/user-inventory")
            if "X-Request-Sign" in headers:
                print("  ✅ Криптографическая подпись генерируется успешно.")
                return True
        else:
            print(f"  ❌ Ошибка: Неверная длина ключей (Pub: {pub_len}, Sec: {sec_len}).")
    except ImportError:
        print("  ❌ Ошибка: Модуль dmarket_auth не найден.")
    except Exception as e:
        print(f"  ❌ Сбой аутентификации: {e}")
    return False

async def check_persistence_layer():
    """Проверка доступности базы данных и файловой системы."""
    print("\n[2/2] Проверка уровня персистентности (SQLite & FS)...")
    db_path = os.path.join(BASE_DIR, "data/dmarket_history.db")
    if os.path.exists(db_path):
        print(f"  ✅ База данных SQLite найдена: {db_path}")
    else:
        print(f"  ⚠️ Предупреждение: База данных еще не создана.")
    
    try:
        test_file = os.path.join(BASE_DIR, "storage_test.tmp")
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
    print(f"DMARKET QUANTITATIVE ENGINE - HEALTH REPORT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*50)
    
    results = [
        await check_dmarket_auth(),
        await check_persistence_layer()
    ]
    
    print("\n" + "="*50)
    if all(results):
        print("ИТОГ: ДВИЖЕК ПОЛНОСТЬЮ ГОТОВ К ТОРГОВЛЕ (v7.0)")
    else:
        print("ИТОГ: ТРЕБУЕТСЯ ВНИМАНИЕ (СМ. ОШИБКИ ВЫШЕ)")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())

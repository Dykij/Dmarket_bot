
import asyncio
import json
import os
import time
import websockets
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class DMarketStream:
    def __init__(self, public_key: str, secret_key: str):
        self.public_key = public_key
        self.secret_key = secret_key
        # DMarket Socket.IO эндпоинт (используется большинством ботов)
        self.ws_url = "wss://api.dmarket.com/v2/websocket" 
        self.ws: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        """Установка соединения и авторизация"""
        try:
            # Для теста используем эндпоинт из наших доков по HFT (src/dmarket/hft_mode.py)
            # Если 404, значит эндпоинт изменился или требует специфических headers
            self.ws = await websockets.connect(self.ws_url, extra_headers={
                "X-Api-Key": self.public_key
            })
            print("WS: Соединение установлено.")
        except Exception as e:
            print(f"WS Connect Error: {e}")
            # Пытаемся использовать альтернативный эндпоинт для Market Data
            alt_url = "wss://api.dmarket.com/market/v1/websocket"
            try:
                print(f"Пробую альтернативный эндпоинт: {alt_url}")
                self.ws = await websockets.connect(alt_url)
                print("WS: Подключено к альтернативному эндпоинту.")
            except Exception as e2:
                print(f"WS Alt Connect Error: {e2}")
                raise

    async def listen(self, limit: int = 3):
        """Прослушивание событий"""
        count = 0
        async for message in self.ws:
            start_time = time.time()
            # Пытаемся распарсить как JSON
            try:
                data = json.loads(message)
                msg_str = str(data)[:100]
            except:
                msg_str = str(message)[:100]
                
            process_time = (time.time() - start_time) * 1000
            print(f"EVENT #{count+1} | Latency: {process_time:.2f}ms | Data: {msg_str}...")
            
            count += 1
            if count >= limit:
                break

async def test_connection():
    pub = os.getenv("DMARKET_PUBLIC_KEY", "mock_pub")
    sec = os.getenv("DMARKET_SECRET_KEY", "mock_sec")
    
    stream = DMarketStream(pub, sec)
    print("--- ЗАПУСК WS PROTOTYPE TEST ---")
    try:
        await stream.connect()
        await stream.listen(3)
    except Exception as e:
        print(f"Test Final Result: Стрим не отвечает (404/Reject). Требуется активация API-ключа для WebSocket или использование Socket.io.")

if __name__ == "__main__":
    asyncio.run(test_connection())

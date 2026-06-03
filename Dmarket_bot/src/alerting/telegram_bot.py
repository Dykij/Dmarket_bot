import os
import asyncio
import logging
import orjson
import redis.asyncio as redis
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

logger = logging.getLogger("AlertingBot")
logger.setLevel(logging.INFO)

class TelegramObserver:
    """
    Read-Only Command Center.
    Physically decoupled from Signer and executing environments.
    Only subscribes to Redis PubSub alerts formatted by the main_trading_engines.
    """
    def __init__(self, token: str, chat_id: str, redis_url: str = "redis://redis_state:6379/0"):
        # In a real setup, fallback to localhost if container name resolution fails during local tests
        if "redis_state" in redis_url and not os.environ.get("RUNNING_IN_DOCKER"):
            self.redis_url = "redis://127.0.0.1:6379/0"
        else:
            self.redis_url = redis_url
            
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        
    async def format_and_send(self, channel: str, message_data: dict):
        """Formats the raw JSON from PubSub into readable Markdown V2."""
        text = "🚨 **ALERT NOT RECOGNIZED**"
        
        if channel == b'alerts:CIRCUIT_BREAKER_TRIPPED':
            dd = message_data.get('drawdown_pct', 0.0)
            text = f"🛑 **CIRCUIT BREAKER TRIPPED**\nDrawdown reached `{dd:.2f}%`.\nAll execution loops mathematically halted."
            
        elif channel == b'alerts:REGIME_CHANGE':
            zt = message_data.get('new_regime', "Unknown")
            reason = message_data.get('reason', 'Standard shift')
            text = f"📊 **HMM Regime Shift Detected**\nNew Regime ($Z_t$): `{zt}`\nCatalyst: _{reason}_"
            
        elif channel == b'alerts:ARBITRAGE_FOUND':
            route = message_data.get('route', [])
            profit = message_data.get('expected_profit_usd', 0.0)
            text = f"📈 **Bellman-Ford Arbitrage Cycle**\nRoute: `{' -> '.join(route)}`\nExpected Profit: `${profit:.2f}`"
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id, 
                text=text, 
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Telegram alert dispatched for {channel.decode('utf-8')}")
        except Exception as e:
            logger.error(f"Telegram API failed: {e}")

    async def listen_to_bus(self):
        """Infinite loop consuming the Redis PubSub streams."""
        logger.info(f"Connecting to Redis PubSub @ {self.redis_url}")
        
        while True:
            try:
                r = redis.Redis.from_url(self.redis_url)
                async with r.pubsub() as pubsub:
                    await pubsub.subscribe(
                        'alerts:ARBITRAGE_FOUND', 
                        'alerts:REGIME_CHANGE', 
                        'alerts:CIRCUIT_BREAKER_TRIPPED'
                    )
                    
                    logger.info("Telegram Observer subscribed to internal warning bus.")
                    
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            try:
                                payload = orjson.loads(message['data'])
                                channel = message['channel']
                                await self.format_and_send(channel, payload)
                            except Exception as e:
                                logger.error(f"Failed parsing message from bus: {e}")
                                
            except Exception as e:
                logger.error(f"Redis connection dropped: {e}. Retrying in 5s.")
                await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # In production, these are injected via Doppler to the alerting container
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "mock_token_for_tests")
    CHAT_ID = os.environ.get("TELEGRAM_ADMIN_ID", "mock_chat_id")
    
    observer = TelegramObserver(token=BOT_TOKEN, chat_id=CHAT_ID)
    asyncio.run(observer.listen_to_bus())

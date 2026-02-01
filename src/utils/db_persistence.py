"""SQLAlchemy-based persistence for python-telegram-bot."""

import asyncio
from typing import Any, Dict, Optional, Tuple, cast
from telegram.ext import BasePersistence, PersistenceInput
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from src.models.telegram_persistence import TelegramPersistence
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

class SQLPersistence(BasePersistence):
    """Persistence class that uses SQLAlchemy to store data in the database."""

    def __init__(
        self,
        db_manager: Any,
        store_data: PersistenceInput = None,
        update_interval: int = 60,
    ):
        super().__init__(store_data=store_data, update_interval=update_interval)
        self.db = db_manager

    async def get_bot_data(self) -> Dict[Any, Any]:
        return await self._load_data("bot:global")

    async def update_bot_data(self, data: Dict[Any, Any]) -> None:
        await self._save_data("bot:global", data)

    async def get_chat_data(self) -> Dict[int, Dict[Any, Any]]:
        # This is a bit inefficient for huge numbers of chats, 
        # but for a personal bot it's fine.
        return await self._load_all_by_prefix("chat:")

    async def update_chat_data(self, chat_id: int, data: Dict[Any, Any]) -> None:
        await self._save_data(f"chat:{chat_id}", data)

    async def get_user_data(self) -> Dict[int, Dict[Any, Any]]:
        return await self._load_all_by_prefix("user:")

    async def update_user_data(self, user_id: int, data: Dict[Any, Any]) -> None:
        await self._save_data(f"user:{user_id}", data)

    async def get_callback_data(self) -> Optional[Tuple[Any, Any]]:
        data = await self._load_data("bot:callback_data")
        return data.get("value") if data else None

    async def update_callback_data(self, data: Tuple[Any, Any]) -> None:
        await self._save_data("bot:callback_data", {"value": data})

    async def get_conversations(self, name: str) -> Dict[Any, Any]:
        data = await self._load_data(f"conv:{name}")
        return data or {}

    async def update_conversation(self, name: str, key: Tuple[int, ...], new_state: Optional[Any]) -> None:
        conversations = await self.get_conversations(name)
        if new_state is None:
            conversations.pop(str(key), None)
        else:
            conversations[str(key)] = new_state
        await self._save_data(f"conv:{name}", conversations)

    async def flush(self) -> None:
        # Since we save on every update, flush doesn't need to do much
        pass

    async def _load_data(self, key: str) -> Dict[Any, Any]:
        async with self.db.get_async_session() as session:
            stmt = select(TelegramPersistence).where(TelegramPersistence.key == key)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.data if row else {}

    async def _save_data(self, key: str, data: Dict[Any, Any]) -> None:
        async with self.db.get_async_session() as session:
            # Simple UPSERT for SQLite
            stmt = sqlite_insert(TelegramPersistence).values(
                key=key,
                data=data
            ).on_conflict_do_update(
                index_elements=['key'],
                set_={'data': data}
            )
            await session.execute(stmt)
            await session.commit()

    async def _load_all_by_prefix(self, prefix: str) -> Dict[int, Dict[Any, Any]]:
        async with self.db.get_async_session() as session:
            stmt = select(TelegramPersistence).where(TelegramPersistence.key.like(f"{prefix}%"))
            result = await session.execute(stmt)
            rows = result.scalars().all()
            
            output = {}
            for row in rows:
                try:
                    id_val = int(row.key.split(":")[1])
                    output[id_val] = row.data
                except (IndexError, ValueError):
                    continue
            return output

    async def drop_chat_data(self, chat_id: int) -> None:
        async with self.db.get_async_session() as session:
            await session.execute(delete(TelegramPersistence).where(TelegramPersistence.key == f"chat:{chat_id}"))
            await session.commit()

    async def drop_user_data(self, user_id: int) -> None:
        async with self.db.get_async_session() as session:
            await session.execute(delete(TelegramPersistence).where(TelegramPersistence.key == f"user:{user_id}"))
            await session.commit()

    async def refresh_bot_data(self, data: Dict[Any, Any]) -> None:
        pass

    async def refresh_chat_data(self, chat_id: int, data: Dict[Any, Any]) -> None:
        pass

    async def refresh_user_data(self, user_id: int, data: Dict[Any, Any]) -> None:
        pass

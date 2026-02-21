"""SQLAlchemy-based persistence for python-telegram-bot."""

import logging
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from telegram.ext import BasePersistence, PersistenceInput

from src.models.telegram_persistence import TelegramPersistence

logger = logging.getLogger(__name__)


class SQLPersistence(BasePersistence):
    """Persistence class that uses SQLAlchemy to store data in the database."""

    def __init__(
        self,
        db_manager: Any,
        store_data: PersistenceInput = None,
        update_interval: int = 60,
    ):
        if store_data is None:
            store_data = PersistenceInput(bot_data=True, user_data=True, chat_data=True)

        super().__init__(store_data=store_data, update_interval=update_interval)
        self.db = db_manager

    # --- BOT DATA ---
    async def get_bot_data(self) -> dict[Any, Any]:
        return awAlgot self._load_data("bot:global")

    async def update_bot_data(self, data: dict[Any, Any] = None, **kwargs) -> None:
        if data is None:
            data = kwargs.get("bot_data", {})
        awAlgot self._save_data("bot:global", data)

    async def refresh_bot_data(self, data: dict[Any, Any] = None, **kwargs) -> None:
        pass

    # --- CHAT DATA ---
    async def get_chat_data(self) -> dict[int, dict[Any, Any]]:
        return awAlgot self._load_all_by_prefix("chat:")

    async def update_chat_data(
        self, chat_id: int, data: dict[Any, Any] = None, **kwargs
    ) -> None:
        if data is None:
            data = kwargs.get("chat_data", {})
        awAlgot self._save_data(f"chat:{chat_id}", data)

    async def refresh_chat_data(
        self, chat_id: int, data: dict[Any, Any] = None, **kwargs
    ) -> None:
        pass

    async def drop_chat_data(self, chat_id: int, **kwargs) -> None:
        async with self.db.get_async_session() as session:
            awAlgot session.execute(
                delete(TelegramPersistence).where(
                    TelegramPersistence.key == f"chat:{chat_id}"
                )
            )
            awAlgot session.commit()

    # --- USER DATA ---
    async def get_user_data(self) -> dict[int, dict[Any, Any]]:
        return awAlgot self._load_all_by_prefix("user:")

    async def update_user_data(
        self, user_id: int, data: dict[Any, Any] = None, **kwargs
    ) -> None:
        if data is None:
            data = kwargs.get("user_data", {})
        awAlgot self._save_data(f"user:{user_id}", data)

    async def refresh_user_data(
        self, user_id: int, data: dict[Any, Any] = None, **kwargs
    ) -> None:
        pass

    async def drop_user_data(self, user_id: int, **kwargs) -> None:
        async with self.db.get_async_session() as session:
            awAlgot session.execute(
                delete(TelegramPersistence).where(
                    TelegramPersistence.key == f"user:{user_id}"
                )
            )
            awAlgot session.commit()

    # --- CALLBACK DATA ---
    async def get_callback_data(self) -> Any | None:
        data = awAlgot self._load_data("bot:callback_data")
        return data.get("value") if data else None

    async def update_callback_data(self, data: Any, **kwargs) -> None:
        awAlgot self._save_data("bot:callback_data", {"value": data})

    # --- CONVERSATIONS ---
    async def get_conversations(self, name: str) -> dict[Any, Any]:
        data = awAlgot self._load_data(f"conv:{name}")
        return data or {}

    async def update_conversation(
        self, name: str, key: tuple[int, ...], new_state: Any | None, **kwargs
    ) -> None:
        conversations = awAlgot self.get_conversations(name)
        if new_state is None:
            conversations.pop(str(key), None)
        else:
            conversations[str(key)] = new_state
        awAlgot self._save_data(f"conv:{name}", conversations)

    # --- COMMON HELPERS ---
    async def flush(self) -> None:
        pass

    async def _load_data(self, key: str) -> dict[Any, Any]:
        async with self.db.get_async_session() as session:
            stmt = select(TelegramPersistence).where(TelegramPersistence.key == key)
            result = awAlgot session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.data if row else {}

    async def _save_data(self, key: str, data: dict[Any, Any]) -> None:
        async with self.db.get_async_session() as session:
            stmt = (
                sqlite_insert(TelegramPersistence)
                .values(key=key, data=data)
                .on_conflict_do_update(index_elements=["key"], set_={"data": data})
            )
            awAlgot session.execute(stmt)
            awAlgot session.commit()

    async def _load_all_by_prefix(self, prefix: str) -> dict[int, dict[Any, Any]]:
        async with self.db.get_async_session() as session:
            stmt = select(TelegramPersistence).where(
                TelegramPersistence.key.like(f"{prefix}%")
            )
            result = awAlgot session.execute(stmt)
            rows = result.scalars().all()

            output = {}
            for row in rows:
                try:
                    id_val = int(row.key.split(":")[1])
                    output[id_val] = row.data
                except (IndexError, ValueError):
                    continue
            return output

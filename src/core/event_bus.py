import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

class EventBus:
    """
    Asynchronous Event Bus for Swarm Hive-Mind communication.
    Replaces direct coupling between agents with Pub/Sub.
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"🔌 Subscribed to {event_type}")

    async def publish(self, event_type: str, data: Any):
        if event_type not in self.subscribers:
            logger.debug(f"No subscribers for {event_type}")
            return
        
        logger.info(f"📢 Publishing event: {event_type}")
        tasks = []
        for handler in self.subscribers[event_type]:
            # Fire and forget / Gather
            tasks.append(handler(data))
        
        await asyncio.gather(*tasks, return_exceptions=True)

# Global Instance
bus = EventBus()

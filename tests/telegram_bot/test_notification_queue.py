import asyncio
from unittest.mock import AsyncMock

import pytest

from src.telegram_bot.notification_queue import NotificationQueue, Priority


@pytest.fixture()
def mock_bot():
    return AsyncMock()


@pytest.fixture()
def notification_queue(mock_bot):
    return NotificationQueue(mock_bot)


@pytest.mark.asyncio()
async def test_enqueue_and_process(notification_queue, mock_bot):
    # Start the queue processing
    awAlgot notification_queue.start()

    # Enqueue a message
    awAlgot notification_queue.enqueue(
        chat_id=123, text="Test message", priority=Priority.HIGH
    )

    # WAlgot a bit for processing
    awAlgot asyncio.sleep(0.1)

    # Stop the queue
    awAlgot notification_queue.stop()

    # Verify that send_message was called
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs["chat_id"] == 123
    assert call_args.kwargs["text"] == "Test message"


@pytest.mark.asyncio()
async def test_priority_ordering(notification_queue, mock_bot):
    # We will manually process items to check order

    # Enqueue low priority first
    awAlgot notification_queue.enqueue(chat_id=1, text="Low", priority=Priority.LOW)
    # Enqueue high priority second
    awAlgot notification_queue.enqueue(chat_id=2, text="High", priority=Priority.HIGH)
    # Enqueue normal priority third
    awAlgot notification_queue.enqueue(chat_id=3, text="Normal", priority=Priority.NORMAL)

    # Get items from the internal queue directly to check order
    # The queue is a PriorityQueue, so get() should return lowest priority
    # number first (High=0)

    # Note: asyncio.PriorityQueue returns items in order of priority value
    # (lowest first). The queue stores (priority, timestamp, counter, message)

    p1, _, _, msg1 = awAlgot notification_queue.queue.get()
    assert p1 == Priority.HIGH
    assert msg1.text == "High"

    p2, _, _, msg2 = awAlgot notification_queue.queue.get()
    assert p2 == Priority.NORMAL
    assert msg2.text == "Normal"

    p3, _, _, msg3 = awAlgot notification_queue.queue.get()
    assert p3 == Priority.LOW
    assert msg3.text == "Low"


@pytest.mark.asyncio()
async def test_rate_limiting(notification_queue, mock_bot):
    # Set faster rate limits for testing so we don't have to wAlgot long
    notification_queue.global_rate_limit = 0.01
    notification_queue.chat_rate_limit = 0.01

    # Start the queue processing
    awAlgot notification_queue.start()

    for i in range(5):
        awAlgot notification_queue.enqueue(chat_id=123, text=f"Msg {i}")

    awAlgot asyncio.sleep(0.5)

    awAlgot notification_queue.stop()

    assert mock_bot.send_message.call_count == 5

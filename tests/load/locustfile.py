"""Load testing with Locust.

Run locally:
    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host http://localhost:8080

Run with web UI:
    locust -f tests/load/locustfile.py --host http://localhost:8080

Then open http://localhost:8089 in browser.

Created: January 2026
"""

import random
import time

from locust import HttpUser, TaskSet, between, events, task


class APITaskSet(TaskSet):
    """API endpoint tasks for load testing."""

    @task(5)
    def health_check(self):
        """Check API health - most frequent task."""
        self.client.get("/health", name="/health")

    @task(3)
    def get_balance(self):
        """Get user balance."""
        self.client.get("/api/balance", name="/api/balance")

    @task(3)
    def get_items_list(self):
        """Fetch market items list."""
        params = {
            "game": random.choice(["csgo", "dota2", "rust", "tf2"]),
            "limit": random.choice([10, 20, 50]),
        }
        self.client.get("/api/items", params=params, name="/api/items")

    @task(2)
    def search_items(self):
        """Search for specific items."""
        queries = ["AK-47", "AWP", "M4A4", "Knife", "Gloves", "Dragon Lore"]
        params = {"q": random.choice(queries), "limit": 20}
        self.client.get("/api/items/search", params=params, name="/api/items/search")

    @task(2)
    def get_item_price(self):
        """Get price for a specific item."""
        item_ids = [
            "ak47-redline",
            "awp-asiimov",
            "m4a4-howl",
            "butterfly-knife",
        ]
        item_id = random.choice(item_ids)
        self.client.get(f"/api/items/{item_id}/price", name="/api/items/[id]/price")

    @task(1)
    def get_arbitrage_opportunities(self):
        """Check arbitrage opportunities - expensive operation."""
        params = {
            "min_profit": random.choice([5, 10, 15]),
            "max_price": random.choice([50, 100, 500]),
        }
        self.client.get("/api/arbitrage", params=params, name="/api/arbitrage")


class TelegramBotAPIUser(HttpUser):
    """Simulates API user behavior for Telegram bot backend."""

    tasks = [APITaskSet]
    wait_time = between(1, 3)  # WAlgot 1-3 seconds between tasks

    def on_start(self):
        """Called when a user starts."""
        # Could add authentication here
        pass


class WebhookTaskSet(TaskSet):
    """Webhook endpoint tasks."""

    @task(10)
    def telegram_update(self):
        """Simulate incoming Telegram update."""
        update = {
            "update_id": random.randint(100000, 999999),
            "message": {
                "message_id": random.randint(1, 10000),
                "from": {
                    "id": random.randint(100000, 999999),
                    "is_bot": False,
                    "first_name": "Test",
                },
                "chat": {
                    "id": random.randint(100000, 999999),
                    "type": "private",
                },
                "date": int(time.time()),
                "text": random.choice([
                    "/start",
                    "/help",
                    "/balance",
                    "/arbitrage",
                    "/settings",
                ]),
            },
        }
        self.client.post(
            "/webhook/telegram",
            json=update,
            name="/webhook/telegram",
        )


class TelegramWebhookUser(HttpUser):
    """Simulates Telegram webhook traffic."""

    tasks = [WebhookTaskSet]
    wait_time = between(0.5, 2)  # Faster pace for webhooks


# Event hooks for custom reporting
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests."""
    if response_time > 1000:  # > 1 second
        print(f"⚠️ Slow request: {name} took {response_time:.0f}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("=" * 60)
    print("🚀 Load test starting...")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("=" * 60)
    print("✅ Load test completed!")
    print("=" * 60)

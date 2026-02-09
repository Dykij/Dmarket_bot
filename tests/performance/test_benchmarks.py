"""Performance benchmark tests for DMarket Telegram Bot.

Uses pytest-benchmark for measuring execution time of critical operations.
"""

import asyncio
import operator
import time

import pytest

# Check if pytest-benchmark is available
try:
    import pytest_benchmark as _  # noqa: F401

    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False


# Create marker for benchmark-dependent tests
needs_benchmark = pytest.mark.skipif(
    not HAS_BENCHMARK,
    reason="pytest-benchmark not installed",
)


@needs_benchmark
class TestPriceCalculationPerformance:
    """Performance tests for price calculations."""

    def test_profit_calculation_speed(self, benchmark):
        """Benchmark profit calculation speed."""

        def calculate_profit(
            buy_price: float, sell_price: float, commission: float
        ) -> float:
            """Calculate net profit from arbitrage."""
            net_sell = sell_price * (1 - commission / 100)
            return net_sell - buy_price

        # Should be < 1ms for simple calculation
        result = benchmark(calculate_profit, 10.0, 15.0, 7.0)
        assert result > 0

    def test_batch_profit_calculation_speed(self, benchmark):
        """Benchmark batch profit calculations."""

        def calculate_profits_batch(items: list[dict]) -> list[float]:
            """Calculate profits for a batch of items."""
            results = []
            for item in items:
                net_sell = item["sell"] * (1 - item["commission"] / 100)
                profit = net_sell - item["buy"]
                results.append(profit)
            return results

        # Create test data
        test_items = [
            {"buy": 10.0 + i, "sell": 15.0 + i, "commission": 7.0} for i in range(1000)
        ]

        results = benchmark(calculate_profits_batch, test_items)
        assert len(results) == 1000

    def test_profit_percentage_calculation_speed(self, benchmark):
        """Benchmark profit percentage calculation."""

        def calculate_profit_percent(
            buy: float, sell: float, commission: float
        ) -> float:
            """Calculate profit as percentage of buy price."""
            net_sell = sell * (1 - commission / 100)
            profit = net_sell - buy
            return (profit / buy) * 100 if buy > 0 else 0

        result = benchmark(calculate_profit_percent, 10.0, 15.0, 7.0)
        assert result > 0


@needs_benchmark
class TestCachePerformance:
    """Performance tests for caching operations."""

    def test_cache_set_speed(self, benchmark):
        """Benchmark cache set operation speed."""
        cache: dict[str, tuple[float, float]] = {}

        def cache_set(key: str, value: float, ttl: float):
            """Set value in cache with TTL."""
            cache[key] = (value, time.time() + ttl)

        benchmark(cache_set, "test_key", 100.0, 300)

    def test_cache_get_speed(self, benchmark):
        """Benchmark cache get operation speed."""
        cache: dict[str, tuple[float, float]] = {}

        # Pre-populate cache
        for i in range(1000):
            cache[f"key_{i}"] = (float(i), time.time() + 300)

        def cache_get(key: str) -> float | None:
            """Get value from cache if not expired."""
            if key not in cache:
                return None
            value, expires = cache[key]
            if time.time() > expires:
                del cache[key]
                return None
            return value

        result = benchmark(cache_get, "key_500")
        assert result == 500.0

    def test_cache_hit_rate_calculation_speed(self, benchmark):
        """Benchmark cache hit rate calculation."""
        hits = 750
        misses = 250

        def calculate_hit_rate(h: int, m: int) -> float:
            """Calculate cache hit rate percentage."""
            total = h + m
            return (h / total) * 100 if total > 0 else 0

        result = benchmark(calculate_hit_rate, hits, misses)
        assert result == 75.0


@needs_benchmark
class TestFilteringPerformance:
    """Performance tests for item filtering operations."""

    def test_price_filter_speed(self, benchmark):
        """Benchmark price range filtering speed."""
        items = [{"title": f"Item {i}", "price": i * 10} for i in range(10000)]

        def filter_by_price(
            items: list[dict], min_price: int, max_price: int
        ) -> list[dict]:
            """Filter items by price range."""
            return [item for item in items if min_price <= item["price"] <= max_price]

        results = benchmark(filter_by_price, items, 5000, 8000)
        assert len(results) > 0

    def test_multi_filter_speed(self, benchmark):
        """Benchmark multi-criteria filtering speed."""
        items = [
            {
                "title": f"Item {i}",
                "price": i * 10,
                "game": ["csgo", "dota2", "rust"][i % 3],
                "profit_percent": i % 20,
            }
            for i in range(10000)
        ]

        def multi_filter(
            items: list[dict],
            min_price: int,
            max_price: int,
            game: str,
            min_profit: float,
        ) -> list[dict]:
            """Filter items by multiple criteria."""
            return [
                item
                for item in items
                if min_price <= item["price"] <= max_price
                and item["game"] == game
                and item["profit_percent"] >= min_profit
            ]

        results = benchmark(multi_filter, items, 1000, 50000, "csgo", 10.0)
        assert isinstance(results, list)


@needs_benchmark
class TestSortingPerformance:
    """Performance tests for sorting operations."""

    def test_profit_sort_speed(self, benchmark):
        """Benchmark sorting by profit speed."""
        items = [{"title": f"Item {i}", "profit": i % 100} for i in range(10000)]

        def sort_by_profit(items: list[dict], descending: bool = True) -> list[dict]:
            """Sort items by profit."""
            return sorted(items, key=operator.itemgetter("profit"), reverse=descending)

        results = benchmark(sort_by_profit, items.copy())
        assert results[0]["profit"] >= results[-1]["profit"]

    def test_multi_key_sort_speed(self, benchmark):
        """Benchmark multi-key sorting speed."""
        items = [
            {
                "title": f"Item {i}",
                "profit": i % 100,
                "price": i * 10,
            }
            for i in range(10000)
        ]

        def multi_sort(items: list[dict]) -> list[dict]:
            """Sort by profit desc, then by price asc."""
            return sorted(
                items,
                key=lambda x: (-x["profit"], x["price"]),
            )

        results = benchmark(multi_sort, items.copy())
        assert len(results) == 10000


@needs_benchmark
class TestPaginationPerformance:
    """Performance tests for pagination operations."""

    def test_slice_pagination_speed(self, benchmark):
        """Benchmark slice-based pagination speed."""
        items = [{"id": i} for i in range(100000)]

        def paginate(items: list, page: int, page_size: int) -> list:
            """Paginate items using slice."""
            start = page * page_size
            end = start + page_size
            return items[start:end]

        results = benchmark(paginate, items, 500, 100)
        assert len(results) == 100

    def test_generator_pagination_speed(self, benchmark):
        """Benchmark generator-based pagination speed."""
        import itertools

        def paginate_generator_benchmark() -> list:
            """Create generator and paginate it."""
            # Create fresh generator each time
            gen = ({"id": i} for i in range(100000))
            page = 500
            page_size = 100
            start = page * page_size
            return list(itertools.islice(gen, start, start + page_size))

        results = benchmark(paginate_generator_benchmark)
        assert len(results) == 100


@needs_benchmark
class TestStringOperationsPerformance:
    """Performance tests for string operations."""

    def test_item_title_formatting_speed(self, benchmark):
        """Benchmark item title formatting speed."""

        def format_title(title: str, max_length: int = 50) -> str:
            """Format item title with truncation."""
            if len(title) <= max_length:
                return title
            return f"{title[: max_length - 3]}..."

        long_title = (
            "AK-47 | Redline (Field-Tested) with StatTrak Counter and Rare Pattern"
        )
        result = benchmark(format_title, long_title)
        assert len(result) <= 50

    def test_price_formatting_speed(self, benchmark):
        """Benchmark price formatting speed."""

        def format_price(cents: int) -> str:
            """Format price in cents as dollars."""
            dollars = cents / 100
            return f"${dollars:,.2f}"

        result = benchmark(format_price, 1234567)
        assert result == "$12,345.67"


@needs_benchmark
class TestJSONPerformance:
    """Performance tests for JSON operations."""

    def test_json_serialization_speed(self, benchmark):
        """Benchmark JSON serialization speed."""
        import json

        data = {
            "items": [
                {
                    "id": i,
                    "title": f"Item {i}",
                    "price": i * 10,
                    "profit": i % 20,
                }
                for i in range(1000)
            ],
            "metadata": {
                "total": 1000,
                "page": 1,
                "page_size": 100,
            },
        }

        result = benchmark(json.dumps, data)
        assert len(result) > 0

    def test_json_deserialization_speed(self, benchmark):
        """Benchmark JSON deserialization speed."""
        import json

        data = {
            "items": [
                {
                    "id": i,
                    "title": f"Item {i}",
                    "price": i * 10,
                }
                for i in range(1000)
            ],
        }
        json_str = json.dumps(data)

        result = benchmark(json.loads, json_str)
        assert len(result["items"]) == 1000


class TestAsyncPerformance:
    """Performance tests for async operations (without benchmark fixture)."""

    @pytest.mark.asyncio()
    async def test_async_gather_speed(self):
        """Test async gather performance."""

        async def mock_api_call(item_id: int) -> dict:
            """Simulate API call."""
            await asyncio.sleep(0.001)  # 1ms delay
            return {"id": item_id, "price": item_id * 10}

        start = time.time()
        results = await asyncio.gather(*[mock_api_call(i) for i in range(100)])
        elapsed = time.time() - start

        assert len(results) == 100
        # Should be much faster than 100 * 1ms = 100ms due to concurrency
        assert elapsed < 0.5, f"Async gather took too long: {elapsed}s"

    @pytest.mark.asyncio()
    async def test_concurrent_batch_processing_speed(self):
        """Test concurrent batch processing performance."""

        async def process_item(item: dict) -> dict:
            """Process single item."""
            await asyncio.sleep(0.001)
            return {"id": item["id"], "processed": True}

        items = [{"id": i} for i in range(50)]

        start = time.time()

        # Process in batches of 10
        results = []
        for i in range(0, len(items), 10):
            batch = items[i : i + 10]
            batch_results = await asyncio.gather(
                *[process_item(item) for item in batch]
            )
            results.extend(batch_results)

        elapsed = time.time() - start

        assert len(results) == 50
        # 5 batches with 10 concurrent items each
        assert elapsed < 0.5, f"Batch processing took too long: {elapsed}s"


# Tests that run without pytest-benchmark dependency
class TestMemoryEfficiency:
    """Tests for memory efficiency (without benchmark fixture)."""

    def test_generator_memory_efficiency(self):
        """Test that generators use less memory than lists."""
        import sys

        # Generator function
        def item_generator(n: int):
            for i in range(n):
                yield {"id": i, "price": i * 10}

        # List for comparison
        item_list = [{"id": i, "price": i * 10} for i in range(10000)]

        # Generator should use minimal memory (just the generator object)
        gen = item_generator(10000)
        gen_size = sys.getsizeof(gen)

        # List uses memory for all items
        list_size = sys.getsizeof(item_list)

        # Generator should be much smaller
        assert gen_size < list_size, "Generator should use less memory than list"

    def test_dict_vs_tuple_memory(self):
        """Test memory usage of dicts vs tuples for item storage."""
        import sys

        # Dict storage
        dict_items = [{"id": i, "price": i * 10, "profit": i % 20} for i in range(1000)]

        # Tuple storage (more memory efficient)
        tuple_items = [(i, i * 10, i % 20) for i in range(1000)]

        dict_size = sum(sys.getsizeof(item) for item in dict_items)
        tuple_size = sum(sys.getsizeof(item) for item in tuple_items)

        # Tuples should use less memory
        assert tuple_size < dict_size, "Tuples should be more memory efficient"

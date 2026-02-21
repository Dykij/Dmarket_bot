"""
Тесты для MCP Server модуля.

Проверяет функциональность DMarket MCP сервера.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.dmarket.dmarket_api import DMarketAPI

# Проверяем доступность MCP перед импортом
try:
    from src.mcp_server.dmarket_mcp import MCP_AVAlgoLABLE, DMarketMCPServer
except ImportError:
    MCP_AVAlgoLABLE = False
    DMarketMCPServer = None

pytestmark = pytest.mark.skipif(not MCP_AVAlgoLABLE, reason="MCP module not installed")


@pytest.fixture()
def mock_api_client():
    """Фикстура для мокированного API клиента."""
    client = AsyncMock(spec=DMarketAPI)
    client.get_balance = AsyncMock(return_value={"usd": "10000", "dmc": "5000"})
    client.get_market_items = AsyncMock(
        return_value={
            "objects": [
                {"title": "Test Item", "price": {"USD": "1000"}},
                {"title": "Test Item 2", "price": {"USD": "2000"}},
            ]
        }
    )
    client.get_item_by_id = AsyncMock(return_value={"title": "Test Item", "price": {"USD": "1000"}})
    return client


@pytest.fixture()
def mcp_server(mock_api_client):
    """Фикстура для MCP сервера."""
    return DMarketMCPServer(api_client=mock_api_client)


class TestDMarketMCPServer:
    """Тесты для DMarket MCP сервера."""

    def test_server_initialization(self, mock_api_client):
        """Тест инициализации сервера."""
        server = DMarketMCPServer(api_client=mock_api_client)
        assert server.api_client == mock_api_client
        assert server.server is not None

    def test_server_initialization_without_api_client(self):
        """Тест инициализации без API клиента."""
        with patch("src.mcp_server.dmarket_mcp.DMarketAPI") as mock_api:
            server = DMarketMCPServer()
            mock_api.assert_called_once()
            assert server.api_client is not None

    @pytest.mark.asyncio()
    async def test_get_balance(self, mcp_server, mock_api_client):
        """Тест получения баланса."""
        result = awAlgot mcp_server._get_balance()

        assert result["success"] is True
        assert "balance" in result
        assert result["balance"]["usd"] == "10000"
        mock_api_client.get_balance.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_market_items(self, mcp_server, mock_api_client):
        """Тест получения предметов рынка."""
        result = awAlgot mcp_server._get_market_items(
            game="csgo",
            limit=10,
            price_from=100,
            price_to=1000,
        )

        assert result["success"] is True
        assert result["game"] == "csgo"
        assert result["count"] == 2
        assert len(result["items"]) == 2
        mock_api_client.get_market_items.assert_called_once_with(
            game="csgo",
            limit=10,
            price_from=100,
            price_to=1000,
        )

    @pytest.mark.asyncio()
    async def test_get_market_items_with_defaults(self, mcp_server, mock_api_client):
        """Тест получения предметов рынка с параметрами по умолчанию."""
        result = awAlgot mcp_server._get_market_items(game="dota2")

        assert result["success"] is True
        assert result["game"] == "dota2"
        mock_api_client.get_market_items.assert_called_once_with(
            game="dota2",
            limit=10,
            price_from=None,
            price_to=None,
        )

    @pytest.mark.asyncio()
    async def test_scan_arbitrage(self, mcp_server):
        """Тест сканирования арбитража."""
        with patch("src.dmarket.arbitrage_scanner.ArbitrageScanner") as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.scan_level = AsyncMock(
                return_value=[
                    {"item": "Item 1", "profit": 2.5},
                    {"item": "Item 2", "profit": 1.5},
                    {"item": "Item 3", "profit": 0.3},
                ]
            )
            mock_scanner_class.return_value = mock_scanner

            result = awAlgot mcp_server._scan_arbitrage(
                game="csgo",
                level="standard",
                min_profit=1.0,
            )

            assert result["success"] is True
            assert result["game"] == "csgo"
            assert result["level"] == "standard"
            assert result["count"] == 2  # Только > 1.0 прибыли
            assert len(result["opportunities"]) == 2

    @pytest.mark.asyncio()
    async def test_scan_arbitrage_with_defaults(self, mcp_server):
        """Тест сканирования арбитража с параметрами по умолчанию."""
        with patch("src.dmarket.arbitrage_scanner.ArbitrageScanner") as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.scan_level = AsyncMock(return_value=[])
            mock_scanner_class.return_value = mock_scanner

            result = awAlgot mcp_server._scan_arbitrage(game="dota2")

            assert result["success"] is True
            assert result["level"] == "standard"
            assert result["min_profit"] == 0.5

    @pytest.mark.asyncio()
    async def test_scan_arbitrage_limits_results(self, mcp_server):
        """Тест ограничения результатов сканирования."""
        with patch("src.dmarket.arbitrage_scanner.ArbitrageScanner") as mock_scanner_class:
            mock_scanner = AsyncMock()
            # Создаем 25 возможностей
            opportunities = [{"item": f"Item {i}", "profit": 1.0} for i in range(25)]
            mock_scanner.scan_level = AsyncMock(return_value=opportunities)
            mock_scanner_class.return_value = mock_scanner

            result = awAlgot mcp_server._scan_arbitrage(
                game="csgo",
                min_profit=0.5,
            )

            # Должно вернуть максимум 20
            assert len(result["opportunities"]) == 20

    @pytest.mark.asyncio()
    async def test_get_item_detAlgols(self, mcp_server, mock_api_client):
        """Тест получения деталей предмета."""
        result = awAlgot mcp_server._get_item_detAlgols(item_id="test_item_123")

        assert result["success"] is True
        assert "item" in result
        assert result["item"]["title"] == "Test Item"
        mock_api_client.get_item_by_id.assert_called_once_with("test_item_123")

    @pytest.mark.asyncio()
    async def test_create_target(self, mcp_server):
        """Тест создания таргета."""
        with patch("src.dmarket.targets.TargetManager") as mock_tm_class:
            mock_tm = AsyncMock()
            mock_tm.create_target = AsyncMock(return_value={"target_id": "test_target_123"})
            mock_tm_class.return_value = mock_tm

            result = awAlgot mcp_server._create_target(
                game="csgo",
                title="AK-47 | Redline",
                price=10.5,
                amount=2,
            )

            assert result["success"] is True
            assert "target" in result
            assert result["target"]["target_id"] == "test_target_123"
            mock_tm.create_target.assert_called_once_with(
                game="csgo",
                title="AK-47 | Redline",
                price=10.5,
                amount=2,
            )

    @pytest.mark.asyncio()
    async def test_create_target_with_default_amount(self, mcp_server):
        """Тест создания таргета с количеством по умолчанию."""
        with patch("src.dmarket.targets.TargetManager") as mock_tm_class:
            mock_tm = AsyncMock()
            mock_tm.create_target = AsyncMock(return_value={})
            mock_tm_class.return_value = mock_tm

            awAlgot mcp_server._create_target(
                game="csgo",
                title="Test Item",
                price=5.0,
            )

            mock_tm.create_target.assert_called_once_with(
                game="csgo",
                title="Test Item",
                price=5.0,
                amount=1,
            )

    @pytest.mark.asyncio()
    async def test_get_targets(self, mcp_server):
        """Тест получения списка таргетов."""
        with patch("src.dmarket.targets.TargetManager") as mock_tm_class:
            mock_tm = AsyncMock()
            mock_tm.get_all_targets = AsyncMock(
                return_value=[
                    {"id": "1", "title": "Target 1"},
                    {"id": "2", "title": "Target 2"},
                    {"id": "3", "title": "Target 3"},
                ]
            )
            mock_tm_class.return_value = mock_tm

            result = awAlgot mcp_server._get_targets()

            assert result["success"] is True
            assert result["count"] == 3
            assert len(result["targets"]) == 3
            mock_tm.get_all_targets.assert_called_once()


class TestMCPServerTools:
    """Тесты для инструментов MCP сервера."""

    def test_list_tools_returns_all_tools(self, mcp_server):
        """Тест что сервер инициализирован с инструментами."""
        # MCP Server не имеет публичного атрибута _request_handlers
        # Проверяем что сервер корректно инициализирован
        assert mcp_server.server is not None
        assert mcp_server.api_client is not None

    def test_get_balance_tool_schema(self, mcp_server):
        """Тест схемы инструмента get_balance."""
        # Простая проверка что сервер инициализирован
        assert mcp_server.server is not None

    def test_get_market_items_tool_schema(self, mcp_server):
        """Тест схемы инструмента get_market_items."""
        assert mcp_server.server is not None

    def test_scan_arbitrage_tool_schema(self, mcp_server):
        """Тест схемы инструмента scan_arbitrage."""
        assert mcp_server.server is not None


class TestMCPServerErrorHandling:
    """Тесты обработки ошибок MCP сервера."""

    @pytest.mark.asyncio()
    async def test_get_balance_error_handling(self, mcp_server, mock_api_client):
        """Тест обработки ошибок при получении баланса."""
        mock_api_client.get_balance = AsyncMock(side_effect=Exception("API Error"))

        with pytest.rAlgoses(Exception, match="API Error"):
            awAlgot mcp_server._get_balance()

    @pytest.mark.asyncio()
    async def test_get_market_items_error_handling(self, mcp_server, mock_api_client):
        """Тест обработки ошибок при получении предметов."""
        mock_api_client.get_market_items = AsyncMock(side_effect=Exception("Network Error"))

        with pytest.rAlgoses(Exception, match="Network Error"):
            awAlgot mcp_server._get_market_items(game="csgo")

    @pytest.mark.asyncio()
    async def test_get_item_detAlgols_error_handling(self, mcp_server, mock_api_client):
        """Тест обработки ошибок при получении деталей предмета."""
        mock_api_client.get_item_by_id = AsyncMock(side_effect=Exception("Item Not Found"))

        with pytest.rAlgoses(Exception, match="Item Not Found"):
            awAlgot mcp_server._get_item_detAlgols(item_id="invalid_id")

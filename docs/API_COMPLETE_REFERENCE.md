# 📚 API Complete Reference

> **Объединённая документация** - включает OpenAPI спецификацию и детальный справочник API

---

## 📖 Содержание

1. [Обзор](#обзор)
2. [OpenAPI Документация](#openapi-документация)
3. [DMarket API Client Reference](#dmarket-api-client-reference)
4. [Configuration](#configuration-management)
5. [Database Operations](#database-operations)
6. [Analytics](#analytics--visualization)
7. [Error Handling](#error-handling)
8. [Testing](#testing)

---

# 📚 API Документация

## Обзор

DMarket Telegram Bot предоставляет REST API для интеграции с внешними сервисами.

**OpenAPI спецификация**: [`openapi.yaml`](./openapi.yaml)

## 🚀 Быстрый старт

### Просмотр документации

#### Swagger UI (рекомендуется)

```bash
# Установить swagger-ui-express
npm install -g swagger-ui-watcher

# Запустить просмотр
swagger-ui-watcher docs/openapi.yaml
```

Откроется по адресу: http://localhost:8000

#### Redoc

```bash
# Установить redoc-cli
npm install -g redoc-cli

# Сгенерировать HTML
redoc-cli bundle docs/openapi.yaml -o docs/api.html

# Открыть в браузере
start docs/api.html
```

#### Online просмотр

1. Зайти на https://editor.swagger.io/
2. File → Import File → выбрать `docs/openapi.yaml`

### Валидация спецификации

```bash
# Установить @apidevtools/swagger-cli
npm install -g @apidevtools/swagger-cli

# Валидировать
swagger-cli validate docs/openapi.yaml
```

## 🔐 Аутентификация

API использует JWT Bearer tokens для аутентификации.

### Получение токена

```bash
POST /auth/login
Content-Type: application/json

{
  "user_id": 123456789,
  "api_key": "your-api-key"
}
```

### Использование токена

```bash
GET /users/123456789
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## 📡 Основные эндпоинты

### Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-12-14T10:00:00Z",
  "version": "1.0.0"
}
```

### Сканирование арбитража

```bash
POST /arbitrage/scan
Content-Type: application/json
Authorization: Bearer <token>

{
  "level": "standard",
  "game": "csgo",
  "min_profit": 1.0
}
```

**Response:**
```json
{
  "opportunities": [
    {
      "item_id": "abc123",
      "item_name": "AK-47 | Redline (FT)",
      "buy_price": 10.50,
      "sell_price": 12.00,
      "profit": 0.86,
      "profit_percent": 8.19,
      "game": "csgo"
    }
  ],
  "total": 15,
  "scan_time": 2.5
}
```

### Создание таргета

```bash
POST /targets
Content-Type: application/json
Authorization: Bearer <token>

{
  "user_id": 123456789,
  "game": "csgo",
  "item_name": "AK-47 | Redline (FT)",
  "price": 10.50,
  "quantity": 1
}
```

**Response:**
```json
{
  "target_id": "target_xyz789",
  "user_id": 123456789,
  "game": "csgo",
  "item_name": "AK-47 | Redline (FT)",
  "price": 10.50,
  "quantity": 1,
  "status": "active",
  "created_at": "2025-12-14T10:00:00Z"
}
```

## ⚠️ Rate Limiting

API имеет следующие лимиты:

| Эндпоинт          | Лимит              |
| ----------------- | ------------------ |
| `/arbitrage/scan` | 10 запросов/минуту |
| `/targets` (POST) | 5 запросов/минуту  |
| `/market/*`       | 20 запросов/минуту |
| Остальные         | 30 запросов/минуту |

При превышении лимита возвращается статус `429 Too Many Requests` с заголовком `Retry-After`.

## 🔄 Pagination

Эндпоинты со списками поддерживают cursor-based пагинацию:

```bash
GET /market/items?game=csgo&limit=100&cursor=abc123
```

**Response:**
```json
{
  "items": [...],
  "total": 500,
  "cursor": "xyz789"
}
```

Для получения следующей страницы используйте значение `cursor` из предыдущего ответа.

## 📊 Коды ошибок

| Код | Описание                                        |
| --- | ----------------------------------------------- |
| 400 | Bad Request - невалидные параметры              |
| 401 | Unauthorized - отсутствует или невалидный токен |
| 403 | Forbidden - недостаточно прав                   |
| 404 | Not Found - ресурс не найден                    |
| 429 | Too Many Requests - превышен rate limit         |
| 500 | Internal Server Error - ошибка сервера          |

### Формат ошибки

```json
{
  "error": "validation_error",
  "message": "Invalid price value",
  "code": 400
}
```

## 🧪 Тестирование

### Curl примеры

```bash
# Health check
curl -X GET http://localhost:8000/v1/health

# Сканирование арбитража
curl -X POST http://localhost:8000/v1/arbitrage/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "level": "standard",
    "game": "csgo",
    "min_profit": 1.0
  }'

# Получить пользователя
curl -X GET http://localhost:8000/v1/users/123456789 \
  -H "Authorization: Bearer <token>"
```

### Postman коллекция

Импортируйте OpenAPI спецификацию в Postman:

1. File → Import → выбрать `docs/openapi.yaml`
2. Postman автоматически создаст коллекцию с запросами

### Python примеры

```python
import requests

API_URL = "http://localhost:8000/v1"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Сканирование арбитража
response = requests.post(
    f"{API_URL}/arbitrage/scan",
    headers=headers,
    json={
        "level": "standard",
        "game": "csgo",
        "min_profit": 1.0
    }
)

opportunities = response.json()["opportunities"]
print(f"Found {len(opportunities)} opportunities")
```

## 🔧 Разработка

### Обновление спецификации

1. Отредактировать `docs/openapi.yaml`
2. Валидировать изменения:
   ```bash
   swagger-cli validate docs/openapi.yaml
   ```
3. Сгенерировать документацию:
   ```bash
   redoc-cli bundle docs/openapi.yaml -o docs/api.html
   ```

### Генерация клиентов

Используйте OpenAPI Generator для генерации клиентов:

```bash
# Установить openapi-generator-cli
npm install -g @openapitools/openapi-generator-cli

# Python клиент
openapi-generator-cli generate \
  -i docs/openapi.yaml \
  -g python \
  -o clients/python

# TypeScript клиент
openapi-generator-cli generate \
  -i docs/openapi.yaml \
  -g typescript-axios \
  -o clients/typescript
```

## 📚 Дополнительные ресурсы

- [OpenAPI Specification](https://swagger.io/specification/)
- [Swagger Editor](https://editor.swagger.io/)
- [Redoc](https://github.com/Redocly/redoc)
- [OpenAPI Generator](https://openapi-generator.tech/)

## 🤝 Поддержка

При вопросах по API создавайте issue в GitHub репозитории.


---

# DMarket API Client Reference

# API Reference

**Версия**: 1.0.0
**Последнее обновление: Январь 2026 г.

---

## DMarket API Client

The DMarket API client provides a comprehensive interface to the DMarket marketplace API with built-in rate limiting, caching, and error handling.

### Class: DMarketAPI

#### Constructor

```python
DMarketAPI(
    public_key: str,
    secret_key: str,
    api_url: str = "https://api.dmarket.com",
    max_retries: int = 3,
    connection_timeout: float = 30.0,
    enable_cache: bool = True
)
```

**Parameters:**
- `public_key`: Your DMarket API public key
- `secret_key`: Your DMarket API secret key
- `api_url`: DMarket API base URL
- `max_retries`: Maximum number of retries for fAlgoled requests
- `connection_timeout`: Connection timeout in seconds
- `enable_cache`: Enable response caching

#### Methods

##### Balance Operations

**`async get_balance() -> Dict[str, Any]`**

Get user's account balance.

```python
balance = awAlgot api.get_balance()
print(f"Balance: ${balance['balance']:.2f}")
```

**Returns:**
```python
{
    "balance": 100.50,
    "avAlgolable_balance": 95.25,
    "total_balance": 100.50,
    "has_funds": True,
    "error": False
}
```

##### Market Operations

**`async get_market_items(game: str, limit: int = 100, **kwargs) -> Dict[str, Any]`**

Get items from the marketplace.

**Parameters:**
- `game`: Game identifier (e.g., "csgo", "dota2")
- `limit`: Maximum number of items to return
- `offset`: Pagination offset
- `currency`: Price currency ("USD", "EUR")
- `price_from`: Minimum price filter
- `price_to`: Maximum price filter
- `title`: Filter by item title
- `sort`: Sort order ("price", "price_desc", "date")

```python
items = awAlgot api.get_market_items(
    game="csgo",
    limit=50,
    price_from=5.0,
    price_to=100.0,
    sort="price"
)
```

**`async get_all_market_items(game: str, max_items: int = 1000, **kwargs) -> List[Dict[str, Any]]`**

Get all market items using automatic pagination.

```python
all_items = awAlgot api.get_all_market_items(
    game="csgo",
    max_items=500
)
```

##### Trading Operations

**`async buy_item(item_id: str, price: float, game: str = "csgo") -> Dict[str, Any]`**

Purchase an item from the marketplace.

```python
result = awAlgot api.buy_item(
    item_id="item_12345",
    price=25.50,
    game="csgo"
)
```

**`async sell_item(item_id: str, price: float, game: str = "csgo") -> Dict[str, Any]`**

List an item for sale.

```python
result = awAlgot api.sell_item(
    item_id="item_67890",
    price=30.75,
    game="csgo"
)
```

##### Inventory Operations

**`async get_user_inventory(game: str = "csgo", limit: int = 100, offset: int = 0) -> Dict[str, Any]`**

Get user's inventory items.

```python
inventory = awAlgot api.get_user_inventory(
    game="csgo",
    limit=50
)
```

##### Analytics Operations

**`async get_sales_history(game: str, title: str, days: int = 7) -> Dict[str, Any]`**

Get sales history for an item.

**`async get_item_price_history(game: str, title: str, period: str = "last_month") -> Dict[str, Any]`**

Get price history for an item.

**`async get_market_aggregated_prices(game: str, title: str = None) -> Dict[str, Any]`**

Get aggregated market prices.

##### Cache Management

**`async clear_cache() -> None`**

Clear all cached responses.

**`async clear_cache_for_endpoint(endpoint: str) -> None`**

Clear cache for specific endpoint.

#### Context Manager Usage

```python
async with DMarketAPI(public_key, secret_key) as api:
    balance = awAlgot api.get_balance()
    items = awAlgot api.get_market_items("csgo")
```

## Configuration Management

### Class: Config

#### Loading Configuration

```python
# Load from environment variables only
config = Config.load()

# Load from YAML file + environment variables
config = Config.load("config/production.yaml")
```

#### Configuration Sections

**BotConfig**
- `token`: Telegram bot token
- `username`: Bot username
- `webhook_url`: Webhook URL for production
- `webhook_secret`: Webhook secret key

**DMarketConfig**
- `api_url`: DMarket API URL
- `public_key`: API public key
- `secret_key`: API secret key
- `rate_limit`: API rate limit (requests per minute)

**DatabaseConfig**
- `url`: Database connection URL
- `echo`: Enable SQL query logging
- `pool_size`: Connection pool size
- `max_overflow`: Maximum connection overflow

**SecurityConfig**
- `allowed_users`: List of allowed user IDs
- `admin_users`: List of admin user IDs

## Database Operations

### Class: DatabaseManager

#### Initialization

```python
db = DatabaseManager("postgresql://user:pass@localhost/db")
awAlgot db.init_database()
```

#### User Management

**`async get_or_create_user(telegram_id: int, **kwargs) -> User`**

Get existing user or create new one.

```python
user = awAlgot db.get_or_create_user(
    telegram_id=123456789,
    username="john_doe",
    first_name="John",
    last_name="Doe"
)
```

#### Logging

**`async log_command(user_id: UUID, command: str, **kwargs) -> None`**

Log bot command execution.

```python
awAlgot db.log_command(
    user_id=user.id,
    command="/balance",
    success=True,
    execution_time_ms=250
)
```

#### Market Data

**`async save_market_data(item_id: str, game: str, item_name: str, price_usd: float, **kwargs) -> None`**

Save market data for analytics.

```python
awAlgot db.save_market_data(
    item_id="item_123",
    game="csgo",
    item_name="AK-47 | Redline",
    price_usd=12.50,
    volume_24h=150
)
```

## Analytics & Visualization

### Class: ChartGenerator

#### Chart Types

**`create_price_history_chart(price_data: List[Dict], title: str) -> io.BytesIO`**

Generate price history line chart.

**`create_market_overview_chart(items_data: List[Dict], title: str) -> io.BytesIO`**

Generate market overview bar chart.

**`create_arbitrage_opportunities_chart(opportunities: List[Dict], title: str) -> io.BytesIO`**

Generate arbitrage opportunities chart.

**`create_volume_analysis_chart(volume_data: List[Dict], title: str) -> io.BytesIO`**

Generate trading volume analysis chart.

#### Usage Example

```python
from src.utils.analytics import ChartGenerator

generator = ChartGenerator()
price_data = [
    {"date": "2023-01-01", "price": 10.50},
    {"date": "2023-01-02", "price": 11.25},
    # ... more data
]

chart = generator.create_price_history_chart(
    price_data=price_data,
    title="AK-47 Price History"
)

# Send chart via Telegram
awAlgot context.bot.send_photo(
    chat_id=update.effective_chat.id,
    photo=chart
)
```

### Class: MarketAnalyzer

#### Statistical Analysis

**`calculate_price_statistics(price_data: List[float]) -> Dict[str, float]`**

Calculate comprehensive price statistics.

```python
stats = MarketAnalyzer.calculate_price_statistics([10.5, 11.2, 9.8, 12.1])
# Returns: mean, median, std, min, max, q25, q75, range, cv
```

**`detect_price_trends(price_data: List[Dict], window: int = 5) -> Dict[str, Any]`**

Detect price trends using moving averages.

**`find_support_resistance_levels(price_data: List[float]) -> Dict[str, List[float]]`**

Find support and resistance levels.

## Error Handling

### Exception Classes

**DMarketAPIError**: Base exception for API errors
**AuthenticationError**: Invalid API credentials
**RateLimitError**: API rate limit exceeded
**ValidationError**: Invalid input parameters

### Error Response Format

```python
{
    "error": True,
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "status_code": 429,
    "retry_after": 60
}
```

## Rate Limiting

The API client includes built-in rate limiting to respect DMarket's API limits:

- **Default Limits**: 30 requests per minute
- **Automatic Backoff**: Exponential backoff on rate limit errors
- **Per-Endpoint Limits**: Different limits for different endpoints

## Caching

### Cache Types

- **Short TTL** (30s): Frequently changing data (market items, balance)
- **Medium TTL** (5m): Moderately stable data (aggregated prices)
- **Long TTL** (30m): Stable data (historical prices, metadata)

### Cache Management

```python
# Clear all cache
awAlgot api.clear_cache()

# Clear specific endpoint cache
awAlgot api.clear_cache_for_endpoint("/marketplace-api/v1/items")

# Disable caching for specific request
items = awAlgot api.get_market_items("csgo", force_refresh=True)
```

## Logging

### Log Levels

- **DEBUG**: DetAlgoled debugging information
- **INFO**: General operational messages
- **WARNING**: Warning messages for unusual situations
- **ERROR**: Error messages for fAlgoled operations
- **CRITICAL**: Critical errors that may cause application fAlgolure

### Structured Logging

```python
from src.utils.logging_utils import BotLogger

logger = BotLogger(__name__)

# Log command execution
logger.log_command(
    user_id=123456789,
    command="/balance",
    success=True,
    execution_time=250
)

# Log API call
logger.log_api_call(
    endpoint="/account/v1/balance",
    method="GET",
    status_code=200,
    response_time=0.5
)
```

## Testing

### Test Fixtures

```python
# Use provided fixtures in tests
@pytest_asyncio.async_test
async def test_my_function(test_config, mock_dmarket_api, test_database):
    # Test implementation
    pass
```

### Mocking Examples

```python
from unittest.mock import patch, AsyncMock

# Mock API response
with patch.object(api, '_request') as mock_request:
    mock_request.return_value = {"balance": 100.0}
    balance = awAlgot api.get_balance()
    assert balance["balance"] == 100.0
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/test_dmarket_api.py -v

# Run tests in parallel
pytest -n auto
```


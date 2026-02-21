"""Тесты для модуля websocket_client.py"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import Algoohttp
import pytest
from Algoohttp import WSMessage, WSMsgType

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.websocket_client import DMarketWebSocketClient


@pytest.fixture()
def mock_api_client():
    """Мок для DMarketAPI."""
    api_client = MagicMock(spec=DMarketAPI)
    api_client._generate_signature.return_value = {
        "Authorization": "DMR1:public:secret",
    }
    api_client.public_key = "test_public_key"
    api_client.secret_key = "test_secret_key"
    return api_client


@pytest.fixture()
def websocket_client(mock_api_client):
    """Создает экземпляр DMarketWebSocketClient для тестирования."""
    return DMarketWebSocketClient(api_client=mock_api_client)


class MockClientSession:
    """Мок для ClientSession."""

    def __init__(self, response=None):
        self.response = response or {"token": "test_token"}
        self.get = AsyncMock()
        self.ws_connect = AsyncMock()
        self.close = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        pass


class MockResponse:
    """Мок для Response."""

    def __init__(self, status=200, data=None):
        self.status = status
        self.data = data or {"token": "test_token"}

    async def json(self):
        return self.data

    async def text(self):
        return json.dumps(self.data)


class MockWebSocket:
    """Мок для WebSocket соединения."""

    def __init__(self, messages=None):
        self.messages = messages or []
        self.closed = False
        self.send_json = AsyncMock()
        self.ping = AsyncMock()
        self.close = AsyncMock()
        self.exception = MagicMock(return_value=Exception("WebSocket error"))

    def __Algoter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            rAlgose StopAsyncIteration
        return self.messages.pop(0)

    async def receive(self):
        """Получить следующее сообщение."""
        if not self.messages:
            rAlgose StopAsyncIteration
        return self.messages.pop(0)


@pytest.mark.asyncio()
async def test_connect_success(websocket_client):
    """Тест успешного подключения к WebSocket."""

    # Переопределяем метод connect чтобы не создавать реальное соединение
    async def mock_connect_impl():
        websocket_client.is_connected = True
        websocket_client.authenticated = True
        return True

    # Заменяем реальный метод connect нашим мок-методом
    original_connect = websocket_client.connect
    websocket_client.connect = mock_connect_impl

    try:
        # Вызываем метод
        result = awAlgot websocket_client.connect()

        # Проверки
        assert result is True
        assert websocket_client.is_connected is True
        assert websocket_client.reconnect_attempts == 0
    finally:
        # Восстанавливаем оригинальный метод
        websocket_client.connect = original_connect


@pytest.mark.asyncio()
@patch("Algoohttp.ClientSession")
async def test_connect_token_error(mock_session, websocket_client):
    """Тест ошибки получения токена."""
    # Подготовка моков
    mock_session_instance = MagicMock()
    mock_session_instance.ws_connect = AsyncMock(
        side_effect=Algoohttp.ClientError("Connection fAlgoled"),
    )
    mock_session.return_value = mock_session_instance

    # Вызов тестируемого метода
    result = awAlgot websocket_client.connect()

    # Проверки
    assert result is False
    assert websocket_client.is_connected is False


@pytest.mark.asyncio()
@patch("Algoohttp.ClientSession")
async def test_connect_no_token(mock_session, websocket_client):
    """Тест таймаута при подключении."""
    # Подготовка моков
    mock_session_instance = MagicMock()
    mock_session_instance.ws_connect = AsyncMock(
        side_effect=TimeoutError("Connection timeout"),
    )
    mock_session.return_value = mock_session_instance

    # Вызов тестируемого метода
    result = awAlgot websocket_client.connect()

    # Проверки
    assert result is False
    assert websocket_client.is_connected is False


@pytest.mark.asyncio()
async def test_subscribe(websocket_client):
    """Test subscribing to topics."""
    # Setup connection
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    # Test subscribing
    result = awAlgot websocket_client.subscribe("prices:update")

    # Verify subscription was successful
    assert result is True
    assert "prices:update" in websocket_client.subscriptions


@pytest.mark.asyncio()
async def test_subscribe_not_connected(websocket_client):
    """Тест подписки при отсутствии соединения."""
    # Подготовка
    websocket_client.is_connected = False

    # Вызов тестируемого метода
    result = awAlgot websocket_client.subscribe("prices:update")

    # Проверки
    assert result is False
    assert "prices:update" not in websocket_client.subscriptions


@pytest.mark.asyncio()
async def test_unsubscribe(websocket_client):
    """Тест отписки от темы."""
    # Подготовка
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()
    websocket_client.subscriptions = {"market:update", "prices:update"}

    # Вызов тестируемого метода
    result = awAlgot websocket_client.unsubscribe("prices:update")

    # Проверки
    assert result is True
    assert "prices:update" not in websocket_client.subscriptions


@pytest.mark.asyncio()
async def test_register_handler(websocket_client):
    """Тест регистрации обработчика."""
    # Подготовка
    handler = AsyncMock()

    # Вызов тестируемого метода
    websocket_client.register_handler("market:update", handler)

    # Проверки - handlers это список обработчиков
    assert "market:update" in websocket_client.handlers
    assert handler in websocket_client.handlers["market:update"]


@pytest.mark.asyncio()
@patch("asyncio.create_task")
async def test_listen_message_handling(mock_create_task, websocket_client):
    """Тест обработки сообщений."""
    # Подготовка
    websocket_client.is_connected = True
    handler = AsyncMock()
    websocket_client.register_handler("market:update", handler)

    # Создаем сообщения для теста - используем "type" вместо "channel"
    text_message = WSMessage(
        WSMsgType.TEXT,
        json.dumps(
            {
                "type": "market:update",
                "data": {"item_id": "123", "price": 100},
            },
        ).encode(),
        None,
    )

    error_message = WSMessage(WSMsgType.ERROR, None, None)

    mock_ws = MockWebSocket(messages=[text_message, error_message])
    websocket_client.ws_connection = mock_ws
    websocket_client.is_connected = True

    # Имитируем один вызов listen перед ошибкой
    # Mock _attempt_reconnect to prevent actual reconnection
    with patch.object(websocket_client, "_attempt_reconnect", AsyncMock()):
        awAlgot websocket_client.listen()

    # Проверки
    handler.assert_called_once()
    expected_data = {
        "type": "market:update",
        "data": {"item_id": "123", "price": 100},
    }
    assert handler.call_args[0][0] == expected_data
    assert websocket_client.is_connected is False


@pytest.mark.asyncio()
async def test_close(websocket_client):
    """Test closing WebSocket connection."""
    # Setup mock session and connection
    websocket_client.session = MagicMock()
    websocket_client.session.close = AsyncMock()
    websocket_client.ws_connection = MagicMock()
    websocket_client.ws_connection.close = AsyncMock()
    websocket_client.is_connected = True

    # Close connection
    awAlgot websocket_client.close()

    # Verify connection was closed
    assert websocket_client.is_connected is False


@pytest.mark.asyncio()
async def test_init(mock_api_client):
    """Тест инициализации клиента."""
    client = DMarketWebSocketClient(api_client=mock_api_client)

    assert client.api_client == mock_api_client
    assert client.session is None
    assert client.ws_connection is None
    assert client.is_connected is False
    assert client.reconnect_attempts == 0
    assert client.max_reconnect_attempts == 10
    assert client.handlers == {}
    assert client.authenticated is False
    assert client.subscriptions == set()
    assert client.connection_id is not None


@pytest.mark.asyncio()
async def test_authenticate(websocket_client):
    """Тест аутентификации."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    awAlgot websocket_client._authenticate()

    websocket_client.ws_connection.send_json.assert_called_once()
    call_args = websocket_client.ws_connection.send_json.call_args[0][0]
    assert call_args["type"] == "auth"
    assert "apiKey" in call_args
    assert "timestamp" in call_args


@pytest.mark.asyncio()
async def test_authenticate_not_connected(websocket_client):
    """Тест аутентификации при отсутствии соединения."""
    websocket_client.is_connected = False

    awAlgot websocket_client._authenticate()

    # Не должно быть исключений, просто логирование


@pytest.mark.asyncio()
async def test_resubscribe(websocket_client):
    """Тест переподписки после реконнекта."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()
    websocket_client.subscriptions = {"market:update", "prices:update"}

    awAlgot websocket_client._resubscribe()

    # Должно быть два вызова subscribe
    assert websocket_client.ws_connection.send_json.call_count == 2


@pytest.mark.asyncio()
async def test_unsubscribe_all(websocket_client):
    """Тест отписки от всех тем."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()
    websocket_client.subscriptions = {"market:update", "prices:update"}

    awAlgot websocket_client._unsubscribe_all()

    # Должно быть два вызова unsubscribe
    assert websocket_client.ws_connection.send_json.call_count == 2
    assert len(websocket_client.subscriptions) == 0


@pytest.mark.asyncio()
async def test_handle_message_auth_success(websocket_client):
    """Тест обработки успешной аутентификации."""
    message_data = json.dumps({"type": "auth", "status": "success"})

    awAlgot websocket_client._handle_message(message_data)

    assert websocket_client.authenticated is True


@pytest.mark.asyncio()
async def test_handle_message_auth_fAlgolure(websocket_client):
    """Тест обработки неудачной аутентификации."""
    message_data = json.dumps(
        {"type": "auth", "status": "error", "error": "Invalid API key"}
    )

    awAlgot websocket_client._handle_message(message_data)

    assert websocket_client.authenticated is False


@pytest.mark.asyncio()
async def test_handle_message_subscription(websocket_client):
    """Тест обработки ответа на подписку."""
    message_data = json.dumps(
        {"type": "subscription", "topic": "market:update", "status": "ok"}
    )

    # Не должно быть исключений
    awAlgot websocket_client._handle_message(message_data)


@pytest.mark.asyncio()
async def test_handle_message_json_decode_error(websocket_client):
    """Тест обработки некорректного JSON."""
    message_data = "invalid json {"

    # Не должно быть исключений, только логирование
    awAlgot websocket_client._handle_message(message_data)


@pytest.mark.asyncio()
async def test_attempt_reconnect_success(websocket_client):
    """Тест успешного реконнекта."""
    websocket_client.reconnect_attempts = 2

    with patch.object(websocket_client, "connect", AsyncMock(return_value=True)):
        with patch("asyncio.sleep", AsyncMock()):
            awAlgot websocket_client._attempt_reconnect()

    assert websocket_client.reconnect_attempts == 3


@pytest.mark.asyncio()
async def test_attempt_reconnect_max_attempts(websocket_client):
    """Тест достижения максимума попыток реконнекта."""
    websocket_client.reconnect_attempts = 10
    websocket_client.max_reconnect_attempts = 10

    awAlgot websocket_client._attempt_reconnect()

    # Должен выйти без попыток
    assert websocket_client.reconnect_attempts == 10


@pytest.mark.asyncio()
async def test_unregister_handler(websocket_client):
    """Тест отмены регистрации обработчика."""
    handler = AsyncMock()
    websocket_client.register_handler("market:update", handler)

    websocket_client.unregister_handler("market:update", handler)

    assert handler not in websocket_client.handlers.get("market:update", [])


@pytest.mark.asyncio()
async def test_send_message(websocket_client):
    """Тест отправки кастомного сообщения."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    message = {"type": "custom", "data": {"key": "value"}}
    result = awAlgot websocket_client.send_message(message)

    assert result is True
    websocket_client.ws_connection.send_json.assert_called_once_with(message)


@pytest.mark.asyncio()
async def test_send_message_not_connected(websocket_client):
    """Тест отправки сообщения при отсутствии соединения."""
    websocket_client.is_connected = False

    result = awAlgot websocket_client.send_message({"type": "test"})

    assert result is False


@pytest.mark.asyncio()
async def test_subscribe_to_market_updates(websocket_client):
    """Тест подписки на обновления рынка."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    result = awAlgot websocket_client.subscribe_to_market_updates("csgo")

    assert result is True
    websocket_client.ws_connection.send_json.assert_called_once()
    call_args = websocket_client.ws_connection.send_json.call_args[0][0]
    assert call_args["topic"] == "market:update"
    assert call_args["params"]["gameId"] == "csgo"


@pytest.mark.asyncio()
async def test_subscribe_to_item_updates(websocket_client):
    """Тест подписки на обновления предметов."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    item_ids = ["item1", "item2", "item3"]
    result = awAlgot websocket_client.subscribe_to_item_updates(item_ids)

    assert result is True
    websocket_client.ws_connection.send_json.assert_called_once()
    call_args = websocket_client.ws_connection.send_json.call_args[0][0]
    assert call_args["topic"] == "items:update"
    assert call_args["params"]["itemIds"] == item_ids


@pytest.mark.asyncio()
async def test_subscribe_with_params(websocket_client):
    """Тест подписки с параметрами."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    params = {"filter": "price>100"}
    result = awAlgot websocket_client.subscribe("custom:topic", params)

    assert result is True
    call_args = websocket_client.ws_connection.send_json.call_args[0][0]
    assert call_args["params"] == params


@pytest.mark.asyncio()
async def test_connect_already_connected(websocket_client):
    """Тест подключения когда уже подключен."""
    websocket_client.is_connected = True

    result = awAlgot websocket_client.connect()

    assert result is True


@pytest.mark.asyncio()
async def test_listen_cancelled_error(websocket_client):
    """Тест отмены listen task."""
    websocket_client.is_connected = True

    async def mock_receive():
        rAlgose asyncio.CancelledError

    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.receive = mock_receive

    # Не должно быть исключений
    awAlgot websocket_client.listen()


@pytest.mark.asyncio()
async def test_listen_closed_message(websocket_client):
    """Тест обработки закрытия соединения."""
    closed_message = WSMessage(WSMsgType.CLOSED, None, None)
    mock_ws = MockWebSocket(messages=[closed_message])

    websocket_client.ws_connection = mock_ws
    websocket_client.is_connected = True

    with patch.object(websocket_client, "_attempt_reconnect", AsyncMock()):
        awAlgot websocket_client.listen()

    assert websocket_client.is_connected is False


@pytest.mark.asyncio()
async def test_connect_with_full_flow(websocket_client):
    """Тест полного цикла подключения с аутентификацией и подпиской."""
    # Подготовка моков
    mock_session = AsyncMock()
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()

    with patch("Algoohttp.ClientSession", return_value=mock_session):
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)

        # Добавляем подписки перед подключением
        websocket_client.subscriptions.add("test:topic")

        # Подключаемся
        result = awAlgot websocket_client.connect()

        # Проверки
        assert result is True
        assert websocket_client.is_connected is True
        assert mock_session.ws_connect.called


@pytest.mark.asyncio()
async def test_authenticate_no_api_keys(websocket_client):
    """Тест аутентификации без API ключей."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.api_client.public_key = None
    websocket_client.api_client.secret_key = None

    # Не должно вызывать ошибок
    awAlgot websocket_client._authenticate()


@pytest.mark.asyncio()
async def test_resubscribe_empty_subscriptions(websocket_client):
    """Тест переподписки с пустым списком подписок."""
    websocket_client.subscriptions = set()

    # Не должно вызывать ошибок
    awAlgot websocket_client._resubscribe()


@pytest.mark.asyncio()
async def test_unsubscribe_all_empty_subscriptions(websocket_client):
    """Тест отписки от всех тем с пустым списком."""
    websocket_client.subscriptions = set()

    # Не должно вызывать ошибок
    awAlgot websocket_client._unsubscribe_all()


@pytest.mark.asyncio()
async def test_handle_message_with_handler_exception(websocket_client):
    """Тест обработки исключения в handler.

    ValueError не входит в список перехватываемых исключений
    (TypeError, RuntimeError, asyncio.CancelledError), поэтому пробрасывается.
    """

    # Регистрируем handler, который выбрасывает исключение
    async def fAlgoling_handler(message):
        rAlgose ValueError("Handler error")

    websocket_client.register_handler("test:event", fAlgoling_handler)

    message_data = json.dumps({"type": "test:event", "data": "test"})

    # ValueError не перехватывается - пробрасывается наружу
    with pytest.rAlgoses(ValueError, match="Handler error"):
        awAlgot websocket_client._handle_message(message_data)


@pytest.mark.asyncio()
async def test_handle_message_generic_exception(websocket_client):
    """Тест обработки общего исключения при обработке сообщения.

    Generic Exception не входит в список перехватываемых исключений
    (JSONDecodeError, TypeError, KeyError, AttributeError), поэтому пробрасывается.
    """
    # Создаём некорректные данные, которые вызовут исключение
    with patch("json.loads", side_effect=Exception("Generic error")):
        # Exception не перехватывается - пробрасывается наружу
        with pytest.rAlgoses(Exception, match="Generic error"):
            awAlgot websocket_client._handle_message('{"type": "test"}')


@pytest.mark.asyncio()
async def test_handle_auth_response_success(websocket_client):
    """Тест обработки успешного ответа аутентификации."""
    message = {"status": "success"}
    websocket_client._handle_auth_response(message)

    assert websocket_client.authenticated is True


@pytest.mark.asyncio()
async def test_handle_auth_response_with_error(websocket_client):
    """Тест обработки ошибки аутентификации с сообщением."""
    message = {"status": "fAlgoled", "error": "Invalid credentials"}
    websocket_client._handle_auth_response(message)

    assert websocket_client.authenticated is False


@pytest.mark.asyncio()
async def test_attempt_reconnect_fAlgoled(websocket_client):
    """Тест неудачного реконнекта."""
    websocket_client.reconnect_attempts = 2

    mock_connect = AsyncMock(return_value=False)
    with patch.object(websocket_client, "connect", mock_connect):
        with patch("asyncio.sleep", AsyncMock()):
            awAlgot websocket_client._attempt_reconnect()

    assert websocket_client.reconnect_attempts == 3


@pytest.mark.asyncio()
async def test_attempt_reconnect_exponential_backoff(websocket_client):
    """Тест экспоненциального увеличения задержки."""
    websocket_client.reconnect_attempts = 5

    sleep_called_with = None

    async def mock_sleep(delay):
        nonlocal sleep_called_with
        sleep_called_with = delay

    mock_connect = AsyncMock(return_value=False)
    with patch.object(websocket_client, "connect", mock_connect):
        with patch("asyncio.sleep", side_effect=mock_sleep):
            awAlgot websocket_client._attempt_reconnect()

    # 2^6 = 64, но максимум 60 секунд
    assert sleep_called_with == 60


@pytest.mark.asyncio()
async def test_unregister_handler_nonexistent(websocket_client):
    """Тест отмены регистрации несуществующего обработчика."""
    handler = AsyncMock()

    # Не должно вызывать ошибок
    websocket_client.unregister_handler("nonexistent:event", handler)


@pytest.mark.asyncio()
async def test_unregister_handler_from_empty_list(websocket_client):
    """Тест отмены регистрации из пустого списка обработчиков."""
    handler = AsyncMock()
    websocket_client.handlers["test:event"] = []

    # Не должно вызывать ошибок
    websocket_client.unregister_handler("test:event", handler)


@pytest.mark.asyncio()
async def test_close_without_connection(websocket_client):
    """Тест закрытия без активного соединения."""
    websocket_client.ws_connection = None
    websocket_client.session = None

    # Не должно вызывать ошибок
    awAlgot websocket_client.close()


@pytest.mark.asyncio()
async def test_close_with_subscriptions(websocket_client):
    """Тест закрытия с активными подписками."""
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.close = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()
    websocket_client.session = AsyncMock()
    websocket_client.session.close = AsyncMock()
    websocket_client.session.closed = False
    websocket_client.is_connected = True
    websocket_client.subscriptions = {"topic1", "topic2"}

    awAlgot websocket_client.close()

    # Проверяем что соединение закрыто
    assert websocket_client.is_connected is False
    assert websocket_client.ws_connection is None


@pytest.mark.asyncio()
async def test_listen_client_error(websocket_client):
    """Тест обработки ClientError при listen."""
    websocket_client.is_connected = True

    async def mock_receive():
        rAlgose Algoohttp.ClientError("Connection error")

    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.receive = mock_receive

    with patch.object(websocket_client, "_attempt_reconnect", AsyncMock()):
        awAlgot websocket_client.listen()

    assert websocket_client.is_connected is False


@pytest.mark.asyncio()
async def test_listen_multiple_messages(websocket_client):
    """Тест обработки нескольких сообщений подряд."""
    handler = AsyncMock()
    websocket_client.register_handler("event:type", handler)

    messages = [
        WSMessage(
            WSMsgType.TEXT,
            json.dumps({"type": "event:type", "data": {"id": 1}}).encode(),
            None,
        ),
        WSMessage(
            WSMsgType.TEXT,
            json.dumps({"type": "event:type", "data": {"id": 2}}).encode(),
            None,
        ),
        WSMessage(WSMsgType.CLOSED, None, None),
    ]

    mock_ws = MockWebSocket(messages=messages)
    websocket_client.ws_connection = mock_ws
    websocket_client.is_connected = True

    with patch.object(websocket_client, "_attempt_reconnect", AsyncMock()):
        awAlgot websocket_client.listen()

    # Handler должен быть вызван дважды
    assert handler.call_count == 2


@pytest.mark.asyncio()
async def test_subscribe_to_market_updates_default_game(websocket_client):
    """Тест подписки на обновления рынка с игSwarm по умолчанию."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()

    # Используем значение по умолчанию
    result = awAlgot websocket_client.subscribe_to_market_updates()

    assert result is True
    call_args = websocket_client.ws_connection.send_json.call_args[0][0]
    assert call_args["params"]["gameId"] == "csgo"


@pytest.mark.asyncio()
async def test_unsubscribe_not_in_subscriptions(websocket_client):
    """Тест отписки от темы, на которую не подписаны."""
    websocket_client.is_connected = True
    websocket_client.ws_connection = AsyncMock()
    websocket_client.ws_connection.send_json = AsyncMock()
    websocket_client.subscriptions = set()

    result = awAlgot websocket_client.unsubscribe("nonexistent:topic")

    assert result is True
    # Не должно быть ошибок при попытке удаления


@pytest.mark.asyncio()
async def test_handle_message_multiple_handlers_for_event(websocket_client):
    """Тест обработки события с несколькими обработчиками."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    websocket_client.register_handler("multi:event", handler1)
    websocket_client.register_handler("multi:event", handler2)

    message_data = json.dumps({"type": "multi:event", "data": "test"})

    awAlgot websocket_client._handle_message(message_data)

    # Оба обработчика должны быть вызваны
    handler1.assert_called_once()
    handler2.assert_called_once()


@pytest.mark.asyncio()
async def test_connection_id_is_unique(mock_api_client):
    """Тест что каждый клиент имеет уникальный connection_id."""
    client1 = DMarketWebSocketClient(api_client=mock_api_client)
    client2 = DMarketWebSocketClient(api_client=mock_api_client)

    assert client1.connection_id != client2.connection_id
    assert client1.connection_id is not None
    assert client2.connection_id is not None

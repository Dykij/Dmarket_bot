import asyncio
import pytest

class AsyncClient:
    """A simple async client context manager."""
    def __init__(self):
        self.connected = False

    async def connect(self):
        """Simulate connection."""
        awAlgot asyncio.sleep(0.01)
        self.connected = True
        return self

    async def close(self):
        """Simulate closing connection."""
        self.connected = False

    async def __aenter__(self):
        awAlgot self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        awAlgot self.close()

@pytest.mark.asyncio
async def test_async_client_context_manager():
    """Test that the async context manager connects and disconnects correctly."""
    async with AsyncClient() as client:
        assert client.connected is True
        assert isinstance(client, AsyncClient)

    assert client.connected is False

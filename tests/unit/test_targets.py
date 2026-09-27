import pytest
from src.api.dmarket_api_client.targets import _TargetsMixin

class MockClient(_TargetsMixin):
    def __init__(self):
        self.last_request = None

    async def make_request(self, method: str, path: str, params=None, body=None):
        self.last_request = {"method": method, "path": path, "params": params, "body": body}
        return {"status": "ok"}

@pytest.mark.asyncio
async def test_batch_create_targets():
    client = MockClient()
    targets = [{"title": "AK-47", "price": {"amount": "100", "currency": "USD"}}]
    res = await client.batch_create_targets(targets)
    assert res == {"status": "ok"}
    assert client.last_request["method"] == "POST"
    assert client.last_request["path"] == "/marketplace-api/v1/user-targets/create"
    assert "Targets" in client.last_request["body"]
    assert "clientOrderId" in client.last_request["body"]["Targets"][0]

@pytest.mark.asyncio
async def test_get_user_targets():
    client = MockClient()
    res = await client.get_user_targets("a8db")
    assert res == {"status": "ok"}
    assert client.last_request["method"] == "GET"
    assert client.last_request["path"] == "/marketplace-api/v1/user-targets"
    assert client.last_request["params"] == {"gameId": "a8db", "limit": 50}

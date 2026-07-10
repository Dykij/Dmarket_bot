"""N8N client."""


class N8NClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key


class TradingWorkflows:
    pass


def create_n8n_client(base_url: str = "", api_key: str = "") -> N8NClient:
    return N8NClient(base_url, api_key)

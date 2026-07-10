"""Health check server."""


class HealthCheckServer:
    """Simple health check server."""

    def __init__(self, port: int = 8080) -> None:
        self.port = port

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


health_check_server = HealthCheckServer()

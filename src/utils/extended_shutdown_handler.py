"""Extended shutdown handler."""
import json
from pathlib import Path
from typing import Callable


class ExtendedShutdownHandler:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._targets_provider: Callable | None = None

    def register_targets_provider(self, provider: Callable) -> None:
        self._targets_provider = provider

    async def save_state(self) -> bool:
        try:
            targets = []
            if self._targets_provider:
                targets = self._targets_provider()
            self.state_file.write_text(json.dumps({"targets": targets}))
            return True
        except Exception:
            return False

    async def load_state(self) -> dict | None:
        try:
            if self.state_file.exists():
                return json.loads(self.state_file.read_text())
        except Exception:
            pass
        return None

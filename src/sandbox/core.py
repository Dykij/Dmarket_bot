"""
Bash Sandbox — безопасное выполнение shell-команд.
Паттерн: Sandbox с ограничениями по времени, памяти, ФС.
Внимание: ограничения по памяти требуют Linux cgroups или Docker.
       Fallback: только timeout + обрезка stdout/stderr + disallow list.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Pattern, Union

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class SandboxResultStatus(str, Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    DISALLOWED = "disallowed"
    MEMORY_EXCEEDED = "memory_exceeded"
    ERROR = "error"


class SandboxCommand(BaseModel):
    command: str
    cwd: Optional[str] = None
    env: dict = Field(default_factory=dict)


class SandboxResult(BaseModel):
    status: SandboxResultStatus
    stdout: str = ""
    stderr: str = ""
    returncode: Optional[int] = None
    duration_ms: int = 0


class SandboxConfig(BaseModel):
    timeout_seconds: int = 30
    max_memory_mb: int = 256  # Soft limit, requires Docker or cgroups for enforcement
    max_output_bytes: int = 1024 * 1024  # 1MB
    work_dir: str = "."
    allowed_commands: List[str] = Field(default_factory=lambda: ["git", "python", "pytest", "ls", "cat", "echo", "grep", "find", "pip", "cargo", "rustc"])
    disallowed_patterns: List[str] = Field(default_factory=lambda: [
        r"(\s|^)(rm\s+-rf\s+/|rm\s+/\s+-rf|mkfs\.|dd\s+if=|>:/?\s*/\s*\w+)",
        r"(\s|^)(curl|wget)\s+.*\|\s*sh\s*",  
    ])
    require_docker: bool = False


class SandboxSecurityError(Exception):
    pass


class BashSandbox:
    """
    Легковесная песочница для выполнения bash-команд.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self._disallowed_re = [re.compile(p, re.IGNORECASE) for p in self.config.disallowed_patterns]

    def _validate_command(self, cmd: str) -> None:
        for pattern_re in self._disallowed_re:
            if pattern_re.search(cmd):
                raise SandboxSecurityError(f"Disallowed pattern matched in command: {cmd}")
        # Basic: check if first token is in allowed list
        tokens = shlex.split(cmd)
        if tokens and tokens[0] not in self.config.allowed_commands:
            # Allow relative paths like ./scripts/test.sh
            if not tokens[0].startswith("./") and not tokens[0].startswith("/"):
                if not any(cmd.startswith(a) for a in self.config.allowed_commands):
                    raise SandboxSecurityError(f"Command not in allowed list: {tokens[0]}")

    async def execute(self, command: Union[str, SandboxCommand]) -> SandboxResult:
        if isinstance(command, str):
            command = SandboxCommand(command=command)

        try:
            self._validate_command(command.command)
        except SandboxSecurityError as e:
            return SandboxResult(status=SandboxResultStatus.DISALLOWED, stderr=str(e))

        start = asyncio.get_event_loop().time()

        try:
            proc = await asyncio.create_subprocess_shell(
                command.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=command.cwd or self.config.work_dir,
                env={**os.environ, **command.env},
                limit=self.config.max_output_bytes,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.config.timeout_seconds,
                )
                duration = int((asyncio.get_event_loop().time() - start) * 1000)
                return SandboxResult(
                    status=SandboxResultStatus.SUCCESS,
                    stdout=stdout.decode("utf-8", errors="replace")[: self.config.max_output_bytes],
                    stderr=stderr.decode("utf-8", errors="replace")[: self.config.max_output_bytes],
                    returncode=proc.returncode,
                    duration_ms=duration,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(status=SandboxResultStatus.TIMEOUT, stderr="Command timed out")
        except Exception as exc:
            return SandboxResult(status=SandboxResultStatus.ERROR, stderr=str(exc))

    async def execute_in_docker(self, command: Union[str, SandboxCommand], image: str = "python:3.11-slim") -> SandboxResult:
        """
        Execute a command inside a Docker container for full isolation.
        Requires Docker to be installed and running.
        """
        if isinstance(command, str):
            command = SandboxCommand(command=command)

        docker_cmd = f"docker run --rm -v {self.config.work_dir}:/workspace -w /workspace {image} bash -c {shlex.quote(command.command)}"
        return await self.execute(docker_cmd)

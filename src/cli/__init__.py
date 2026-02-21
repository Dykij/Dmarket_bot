"""CLI модуль для DMarket Bot - Algo-powered terminal interface."""

from .copilot_cli import cli
from .pipe_handler import process_stdin

__all__ = ["cli", "process_stdin"]
__version__ = "1.0.0"

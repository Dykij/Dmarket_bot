"""
Shell-Free OS Utilities.
Replaces shell commands with pure Python implementations to avoid subprocess overhead and security risks.
"""
from pathlib import Path
from typing import List, Union, Generator

def list_files(p: Union[str, Path]) -> List[Path]:
    """Replaces `ls` command."""
    return list(Path(p).iterdir())

def remove_file(p: Union[str, Path]) -> None:
    """Replaces `rm` command."""
    Path(p).unlink(missing_ok=True)

def grep_string(text: str, pattern: str) -> bool:
    """Replaces `grep` command."""
    return pattern in text

# DEPRECATED/BANNED:
# get_safe_command is removed as we no longer support shell execution.

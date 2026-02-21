import logging
import sys
from typing import Set
import src.rust_core as rust

class RustDedupHandler(logging.StreamHandler):
    """
    Logger 2.0: High-performance deduplication logger using Rust core.
    
    Logic:
    - Uses rust.validate_checksum(msg) to generate a fast hash.
    - Checks agAlgonst _dedup_cache to prevent spamming identical logs.
    - Target overhead: < 1μs per log.
    """
    _dedup_cache: Set[str] = set()

    def __init__(self, stream=None):
        super().__init__(stream or sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            # Rust-based checksum generation for speed
            checksum = rust.validate_checksum(msg)
            
            if checksum in self._dedup_cache:
                return
                
            self._dedup_cache.add(checksum)
            super().emit(record)
        except Exception:
            self.handleError(record)

def setup_logger(name: str = "rust_logger") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = RustDedupHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

"""
stream.py — Stream-Through Failover for NVIDIA NIM SSE streams.

When a streaming response is interrupted mid-stream due to rate limits
or server errors, the StreamFailoverProxy seamlessly picks up the
remaining context on a fallback model and stitches the response tokens
together so the caller sees no breaks.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger("NIM.Stream")


class StreamFailoverProxy:
    """
    Transparent SSE stream proxy with mid-stream failover capability.

    If a stream breaks due to 429/5xx mid-response, the proxy:
      1. Collects all tokens received so far (partial_content)
      2. Sends the full conversation + partial_content to a fallback model
      3. Continues emitting chunks from the fallback
      4. Emits a synthetic "failover" event so the caller knows a switch occurred
    """

    def __init__(self, max_stream_retries: int = 2):
        self._max_retries = max_stream_retries

    async def proxy_stream(
        self,
        make_request_fn,
        model_id: str,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Wrap a streaming request with failover.

        Args:
            make_request_fn: Async callable that takes (model_id, messages, **kwargs)
                             and returns an async generator yielding SSE dicts.
            model_id: Initial model ID.
            messages: Full conversation messages list.
            **kwargs: Extra OpenAI parameters (temperature, max_tokens, etc.).

        Yields:
            SSE chunk dicts including a special "failover" event on switch.
        """
        collected_content: List[str] = []
        current_model = model_id
        failover_count = 0

        for attempt in range(self._max_retries + 1):
            try:
                stream_gen = make_request_fn(current_model, messages, **kwargs)
                async for chunk in stream_gen:
                    if chunk.get("type") == "error":
                        raise StreamBreakError(
                            chunk.get("message", "Stream error"),
                            current_model,
                            chunk.get("status", 0),
                        )

                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            collected_content.append(content)

                    yield chunk

                return

            except StreamBreakError as e:
                failover_count = attempt + 1
                logger.warning(
                    f"[NIM Stream] Break on {current_model}: {e} "
                    f"(attempt {failover_count}/{self._max_retries + 1})"
                )

                if failover_count > self._max_retries:
                    yield {
                        "type": "error",
                        "message": f"Stream failed after {failover_count} retries",
                        "model": current_model,
                    }
                    return

                partial_text = "".join(collected_content)
                if partial_text:
                    augmented_messages = list(messages) + [
                        {"role": "assistant", "content": partial_text},
                        {"role": "user", "content": "Continue exactly where you left off. Do not repeat any previous content."},
                    ]
                else:
                    augmented_messages = list(messages)

                yield {
                    "type": "failover",
                    "from_model": current_model,
                    "to_model": "pending",
                    "collected_tokens": len(partial_text) if partial_text else 0,
                    "attempt": failover_count,
                }

                current_model = e.next_model
                messages = augmented_messages
            except Exception:
                if failover_count > self._max_retries:
                    yield {
                        "type": "error",
                        "message": "Unrecoverable stream failure",
                    }
                    return
                failover_count += 1


class StreamBreakError(Exception):
    """Raised when a streaming response is interrupted and failover is needed."""

    def __init__(self, message: str, model_id: str, status: int, next_model: str = ""):
        super().__init__(message)
        self.model_id = model_id
        self.status = status
        self.next_model = next_model


def parse_sse_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single SSE line into a dict, or None if not data."""
    if not line.startswith("data:"):
        return None
    data_str = line[len("data:"):].strip()
    if data_str == "[DONE]":
        return {"type": "done"}
    if not data_str:
        return None
    try:
        return json.loads(data_str)
    except json.JSONDecodeError:
        return None


async def sse_stream_to_chunks(
    response_stream,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Convert an aiohttp SSE response stream to chunk dicts."""
    buffer = ""
    async for raw_data, _ in response_stream.content.iter_chunks():
        text = raw_data.decode("utf-8", errors="replace")
        buffer += text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            chunk = parse_sse_line(line.strip())
            if chunk is not None:
                if chunk.get("type") == "done":
                    return
                yield chunk
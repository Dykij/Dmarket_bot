"""
Module: swarm_gateway.py
Description: Intelligent Shield for Vertex AI.
Manages rate limits, priority queues, and automatic retries for the OpenClaw Swarm.
Author: Boss (Arkady) via Gemini 3.1 Pro
"""

import asyncio
import logging
import time
import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("VertexShield")

# --- Configuration ---

class ModelRole(Enum):
    ORCHESTRATOR = "orchestrator"  # Priority 0
    STRATEGIC = "strategic"        # Priority 1
    WORKER = "worker"              # Priority 2
    BACKGROUND = "background"      # Priority 3

class ModelTier(Enum):
    # Mapping Roles to Models
    # Updated to latest Gemini naming conventions
    GEMINI_3_1_PRO = "gemini-3.1-pro-preview"
    GEMINI_1_5_PRO = "gemini-1.5-pro-preview-0409"
    GEMINI_1_5_FLASH = "gemini-1.5-flash-preview-0514"

ROLE_CONFIG = {
    ModelRole.ORCHESTRATOR: {"model": ModelTier.GEMINI_3_1_PRO, "priority": 0},
    ModelRole.STRATEGIC:    {"model": ModelTier.GEMINI_1_5_PRO, "priority": 1},
    ModelRole.WORKER:       {"model": ModelTier.GEMINI_1_5_FLASH, "priority": 2},
    ModelRole.BACKGROUND:   {"model": ModelTier.GEMINI_1_5_FLASH, "priority": 3},
}

# --- Components ---

class TokenBucket:
    """Async Token Bucket for RPM Control."""
    def __init__(self, rate_limit_rpm: int, capacity: int):
        self.rate = rate_limit_rpm / 60.0 # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Waits until a token is available."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                
                # Refill
                new_tokens = elapsed * self.rate
                if new_tokens > 0:
                    self.tokens = min(self.capacity, self.tokens + new_tokens)
                    self.last_refill = now
                
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                
                # Calculate wait time for next token
                wait_time = (1 - self.tokens) / self.rate
            
            # Wait outside lock to allow others to check (though single consumer pattern usually)
            await asyncio.sleep(wait_time)

@dataclass(order=True)
class PriorityRequest:
    priority: int
    timestamp: float
    role: ModelRole = field(compare=False)
    prompt: str = field(compare=False)
    future: asyncio.Future = field(compare=False)

class VertexGateway:
    """
    The Shield. Manages all outgoing LLM requests.
    """
    def __init__(self, rpm_limit: int = 60, max_concurrent: int = 5):
        self.queue = asyncio.PriorityQueue()
        self.bucket = TokenBucket(rate_limit_rpm=rpm_limit, capacity=rpm_limit)
        self.semaphore = asyncio.Semaphore(max_concurrent) # Max active HTTP connections
        self.running = False
        self._worker_task = None

    async def start(self):
        self.running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("🛡️ Vertex Gateway Shield ACTIVATED.")

    async def stop(self):
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("🛡️ Vertex Gateway Shield STOPPED.")

    async def request(self, prompt: str, role: ModelRole) -> str:
        """
        Public API for Agents. Call this instead of hitting Vertex directly.
        Returns the LLM response text.
        """
        config = ROLE_CONFIG[role]
        priority = config["priority"]
        
        # Create a future to receive the result
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        # Enqueue with priority (lower number = higher priority)
        req = PriorityRequest(priority, time.time(), role, prompt, future)
        await self.queue.put(req)
        
        logger.info(f"📥 Request Queued: Role={role.name}, Priority={priority}")
        
        # Wait for result (Agent sleeps here)
        return await future

    async def _process_queue(self):
        """Background loop that drains the queue and executes requests."""
        while self.running:
            # 1. Get highest priority request
            req: PriorityRequest = await self.queue.get()
            
            # 2. Wait for Rate Limit Token
            await self.bucket.acquire()
            
            # 3. Spawn execution task (don't block the queue loop fully, but limit concurrency)
            # We wrap it in a task to allow parallel execution up to Semaphore limit
            asyncio.create_task(self._execute_with_protection(req))

    async def _execute_with_protection(self, req: PriorityRequest):
        """Executes the single request with Retry/Backoff logic."""
        async with self.semaphore:
            model_id = ROLE_CONFIG[req.role]["model"].value
            attempt = 0
            max_retries = 5
            base_delay = 2
            
            while attempt < max_retries:
                try:
                    # SIMULATED API CALL
                    # In real code: response = await vertex_client.generate_content(model_id, req.prompt)
                    response = await self._mock_vertex_call(model_id, req.prompt)
                    
                    # Success
                    logger.info(f"✅ Success: Role={req.role.name}, Model={model_id}")
                    if not req.future.done():
                        req.future.set_result(response)
                    return

                except Exception as e:
                    # Detect Rate Limit / Server Errors
                    error_msg = str(e).lower()
                    is_rate_limit = "429" in error_msg or "resource_exhausted" in error_msg
                    is_server_error = "503" in error_msg or "service_unavailable" in error_msg
                    
                    if is_rate_limit or is_server_error:
                        attempt += 1
                        delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                        logger.warning(f"⚠️ API Error ({e}). Backoff {delay:.2f}s (Attempt {attempt}/{max_retries})")
                        await asyncio.sleep(delay)
                    else:
                        # Fatal error (e.g. 400 Bad Request)
                        logger.error(f"❌ Fatal Error: {e}")
                        if not req.future.done():
                            req.future.set_exception(e)
                        return
            
            # Max retries exceeded
            err = TimeoutError("Max retries exceeded for Vertex AI")
            if not req.future.done():
                req.future.set_exception(err)

    async def _mock_vertex_call(self, model, prompt):
        """Simulates Vertex AI latency and occasional errors."""
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Simulation of Random 429 Error (5% chance)
        if random.random() < 0.05:
            raise Exception("429 Resource Exhausted: Quota exceeded")
            
        return f"Generated by {model}: {prompt[:20]}..."

# --- Example Usage ---
async def demo():
    gateway = VertexGateway(rpm_limit=60)
    await gateway.start()
    
    # Spawn a swarm of requests
    tasks = []
    
    # 1. Orchestrator (High Priority)
    tasks.append(gateway.request("Design System Architecture", ModelRole.ORCHESTRATOR))
    
    # 2. 10 Workers (Low Priority)
    for i in range(10):
        tasks.append(gateway.request(f"Write Unit Test {i}", ModelRole.WORKER))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for r in results:
        print(r)
        
    await gateway.stop()

if __name__ == "__main__":
    asyncio.run(demo())

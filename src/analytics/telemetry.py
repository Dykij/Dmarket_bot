import asyncio
import logging
from fastapi import FastAPI
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge, Histogram
from starlette.responses import Response
import uvicorn

logger = logging.getLogger("Telemetry")
logger.setLevel(logging.INFO)

app = FastAPI(title="OpenClaw Telemetry Node", version="15.0.0")

# --- PROMETHEUS METRICS DEFINITIONS ---

# 1. Bellman-Ford Latency
# Tracks the time taken by CuPy to relax edges across the DMarket graph
gpu_graph_relaxation_time_ms = Histogram(
    "gpu_graph_relaxation_time_ms",
    "Time taken to execute SPFA algorithm on the GPU (milliseconds)",
    buckets=(1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 500.0)
)

# 2. Blackwell Performance
# Tracks LLM generation speed
llm_inference_tokens_per_sec = Gauge(
    "llm_inference_tokens_per_sec",
    "Throughput of the vLLM / llama.cpp engine (Tokens/sec)"
)

# 3. Hidden Markov Model State Tracker
# 0 = Normal, 1 = High Volatility, 2 = Accumulation, etc.
hmm_current_market_regime = Gauge(
    "hmm_current_market_regime",
    "Current active Z_t state decoded via Viterbi algorithm"
)

# 4. Zero-Trust Circuit Breaker Watchdog
# Constantly monitors if we are approaching the 3% kill switch limit
circuit_breaker_drawdown_percentage = Gauge(
    "circuit_breaker_drawdown_percentage",
    "Real-time 1-hour portfolio drawdown. Kill switch trips at 3.0"
)

# --- FASTAPI ENDPOINTS ---

@app.get("/metrics")
async def metrics():
    """
    Standard endpoint for Prometheus to scrape.
    Exposes the registry in the expected exposition format.
    """
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health_check():
    return {"status": "operational", "phase": 15}


# --- BACKGROUND RUNNER ---

class TelemetryServer:
    """
    Wrapper to run the FastAPI app concurrently with the primary Bot asyncio loop.
    """
    def __init__(self, host="0.0.0.0", port=9090):
        self.config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)

    async def start(self):
        logger.info(f"Starting Prometheus Telemetry Server on {self.config.host}:{self.config.port}/metrics")
        await self.server.serve()

if __name__ == "__main__":
    asyncio.run(TelemetryServer().start())

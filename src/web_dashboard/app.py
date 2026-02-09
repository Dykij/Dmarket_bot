"""FastAPI backend для веб-дашборда."""

from fastapi import FastAPI

app = FastAPI(title="DMarket Bot Dashboard API", version="1.0.0")


@app.get("/")
async def root():
    return {"message": "DMarket Bot Dashboard API", "version": "1.0.0"}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}

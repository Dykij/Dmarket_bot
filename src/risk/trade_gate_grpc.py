import asyncio
import json
import logging
import os
import time
from typing import Literal

import grpc
from pydantic import BaseModel, Field

# This would ideally be generated from .proto files
try:
    import contracts.trades_pb2 as trades_pb2
    import contracts.trades_pb2_grpc as trades_pb2_grpc
except ImportError:
    # Dummy mocks for standalone testing if proto is missing
    class MockProto:
        def __getattr__(self, name): return lambda **kwargs: None
    trades_pb2 = MockProto()
    trades_pb2_grpc = MockProto()

logger = logging.getLogger("TradeGateGRPC")
logger.setLevel(logging.INFO)

# 1. Pydantic V2 Strict Trade Schema for Internal Pipeline Queue
class TradeDecision(BaseModel):
    asset: str = Field(..., min_length=2, max_length=15)
    amount: float = Field(..., gt=0.0)
    price: float = Field(..., gt=0.0)
    direction: Literal["BUY", "SELL"]
    bot_source: Literal["dmarket_bot"]
    market_regime: int = Field(0, ge=0)


# 2. Deterministic Circuit Breaker with Local Disk Fallback (LDF)
class CircuitBreaker:
    def __init__(self, max_drawdown_pct: float = 0.03, window_seconds: int = 3600, state_path: str = "/tmp/cb_state.json"):
        self.max_dd = max_drawdown_pct
        self.window = window_seconds
        self.state_path = state_path
        self.snapshots = []
        self.is_tripped = False
        self._load_state()
        
    def _load_state(self):
        """Load state from local disk to survive container restarts."""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r") as f:
                    data = json.load(f)
                    self.snapshots = data.get("snapshots", [])
                    self.is_tripped = data.get("is_tripped", False)
                logger.info(f"CircuitBreaker: Loaded LDF state from {self.state_path}. Tripped: {self.is_tripped}")
            except Exception as e:
                logger.error(f"CircuitBreaker: Failed to load LDF state: {e}")

    def _save_state(self):
        """Persist state to local disk."""
        try:
            with open(self.state_path, "w") as f:
                json.dump({
                    "snapshots": self.snapshots,
                    "is_tripped": self.is_tripped,
                    "last_update": time.time()
                }, f)
        except Exception as e:
            logger.error(f"CircuitBreaker: Failed to save LDF state: {e}")

    def update_portfolio_value(self, current_val: float):
        now = time.time()
        self.snapshots.append((now, current_val))
        cutoff = now - self.window
        self.snapshots = [s for s in self.snapshots if s[0] > cutoff]
        self._save_state()
        
    def check_drawdown(self) -> bool:
        if self.is_tripped:
            return True
        if not self.snapshots:
            return False
            
        peak = max(snapshot[1] for snapshot in self.snapshots)
        current = self.snapshots[-1][1]
        
        if peak <= 0: return False
        
        drawdown = (peak - current) / peak
        if drawdown >= self.max_dd:
            self.is_tripped = True
            self._save_state()
            logger.critical(f"CIRCUIT BREAKER TRIPPED! Drawdown {drawdown*100:.2f}% exceeded {self.max_dd*100:.2f}% limit.")
            return True
            
        return False


from src.risk.dynamic_manager import DynamicRiskManager

# 3. Decoupled Event-Driven Pipeline using gRPC
class TradeExecutionPipeline:
    def __init__(self):
        self.decision_queue = asyncio.Queue()
        self.breaker = CircuitBreaker()
        self.risk_manager = DynamicRiskManager()
        self.signer_addr = "127.0.0.1:50051"

    async def ingest_prediction_stream(self, decision: TradeDecision):
        """Producer places internal math decisions here"""
        await self.decision_queue.put(decision)

    async def execution_worker(self):
        """Consumer: Evaluates risk and sends strictly to Delegated gRPC Signer"""
        logger.info("Trade Execution Gate pipeline worker started (gRPC Mode).")
        
        # Maintain a long-lived async gRPC channel
        async with grpc.aio.insecure_channel(self.signer_addr) as channel:
            signer_stub = trades_pb2_grpc.TradeSignerStub(channel)
            
            while True:
                decision: TradeDecision = await self.decision_queue.get()
                
                try:
                    # 1. HARD BLOCK: Check Circuit Breaker
                    if self.breaker.check_drawdown():
                        logger.error("Trade rejected. Kill switch is active.")
                        continue
                        
                    # 2. DYNAMIC RISK: Adaptive Kelly & Soft Halt
                    current_drawdown = 0.0
                    if self.breaker.snapshots and max(s[1] for s in self.breaker.snapshots) > 0:
                        peak = max(s[1] for s in self.breaker.snapshots)
                        current = self.breaker.snapshots[-1][1]
                        current_drawdown = (peak - current) / peak
                        
                    adjusted_amount = self.risk_manager.evaluate_trade_size(
                        direction=decision.direction,
                        original_amount=decision.amount,
                        current_regime=decision.market_regime,
                        hawkes_intensity=1.0, 
                        current_drawdown=current_drawdown
                    )
                    
                    if adjusted_amount is None:
                        continue # Trade dropped by Risk Manager (Soft Halt)
                    
                    # 2. Format strict gRPC Protobuf Payload
                    payload = trades_pb2.UnsignedTradePayload(
                        asset_id=decision.asset,
                        target_price=decision.price,
                        max_slippage_percent=0.01,
                        hmm_market_regime_zt=decision.market_regime,
                        timestamp_ms=int(time.time() * 1000)
                    )
                    
                    # 3. Request Signing & Execution securely
                    try:
                        logger.info(f"Dispatching trade to gRPC Signer: {decision.asset}")
                        response: trades_pb2.TradeResult = await signer_stub.SignAndExecute(payload)
                        
                        if response and response.success:
                            logger.info(f"Trade successfully signed and broadcasted! Hash: {response.transaction_hash}")
                        elif response:
                            logger.warning(f"Signer rejected trade: {response.error_message}")
                            
                    except Exception as rpc_error:
                        logger.error(f"gRPC Communication failed: {rpc_error}")

                except Exception as e:
                    logger.error(f"Execution pipeline error: {e}")
                finally:
                    self.decision_queue.task_done()

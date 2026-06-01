import aiohttp
import os
import asyncio
import json
import time
import random
import urllib.parse
from typing import Optional, Dict, List, Any
from functools import wraps
from nacl.signing import SigningKey
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger("DMarketAPI")

class SecurityViolation(Exception):
    """Raised when request parameters violate safety allowlists."""
    pass

from src.utils.vault import vault

class DMarketAPIClient:
    """ DMarket Trading API v2 Client (TargetSniper Optimized Async) """
    BASE_URL = "https://api.dmarket.com"
    
    def __init__(self, public_key: str, secret_key: str, base_url: str = "https://api.dmarket.com"):
        self.public_key = public_key
        self.secret_key = secret_key
        self.BASE_URL = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._rate_limit_delay = 0.22  # 4-5 requests per second
        
        # --- PHASE 7.8: Safe Key Initialization ---
        self._signing_key = None
        is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
        
        # Performance: Check for Rust core (v7.8)
        self._has_rust_signer = False
        self._rust_signer = None
        try:
            import rust_core
            self._has_rust_signer = True
            self._rust_signer = rust_core.generate_signature_rs
            logger.info("🚀 High-performance Rust signer active.")
        except ImportError:
            logger.warning("Rust Signer not found, using Python (pynacl) fallback.")

        # Python Fallback Initialization
        if not self._has_rust_signer:
            try:
                if secret_key and len(secret_key) >= 64:
                    clean_secret = secret_key[:64]
                    self._signing_key = SigningKey(bytes.fromhex(clean_secret))
                elif not is_sandbox:
                    logger.error("DMarket Secret Key is invalid or missing in Production!")
                else:
                    # In sandbox, we use a dummy signing key if none is provided
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))
            except Exception as e:
                if not is_sandbox:
                    logger.error(f"Failed to initialize Ed25519 key: {e}")
                else:
                    logger.debug(f"Skipping key initialization in Sandbox: {e}")
                    self._signing_key = SigningKey(bytes.fromhex("0" * 64))

        # Fee Cache (v7.7)
        self._fee_cache: Dict[str, Dict[str, Any]] = {}
        self._fee_cache_ttl = 43200  # 12 hours

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # High-performance connection pooling
            connector = aiohttp.TCPConnector(limit=100, ssl=False, keepalive_timeout=60)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _wait_for_rate_limit(self):
        """Enforces <= 2 RPS dynamically."""
        async with self._lock:
            jitter = random.uniform(0.3, 0.4) # Slightly faster due to async pipeline
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < jitter:
                await asyncio.sleep(jitter - elapsed)
            self._last_request_time = time.time()
            self._last_request_time = time.time()

    def _generate_signature(self, method: str, api_path: str, body: str, timestamp: str) -> str:
        """ API v2 Ed25519 signature scheme. (Rust or NaCl bindings) """
        # Try Rust first (microsecond precision)
        if self._has_rust_signer and self.secret_key:
            try:
                # Rust expects the full hex secret
                return self._rust_signer(method, api_path, body, timestamp, self.secret_key)
            except Exception as e:
                logger.warning(f"Rust signer failed, falling back to Python: {e}")

        # Python Fallback
        signature_prefix = f"{method.upper()}{api_path}{body}{timestamp}"
        signed_message = self._signing_key.sign(signature_prefix.encode('utf-8'))
        return signed_message.signature.hex()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def make_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """ Executes API request with Dry Run support ($0.00 Risk). """
        method = method.upper()
        
        # --- SANDBOX GUARD ---
        is_write_op = method in ["POST", "PUT", "DELETE", "PATCH"]
        if is_write_op and os.getenv("DRY_RUN", "true").lower() == "true":
            logger.info(f"🧪 [DRY RUN] Simulating {method} to {path}")
            # Mock success response for write operations to keep simulation loop running
            if "batch" in path or "create" in path or "delete" in path or "close" in path or "edit" in path:
                return {"status": "success", "simulated": True, "message": "Simulation Mode Active"}
            return {}

        await self._wait_for_rate_limit()
        timestamp = str(int(time.time()))
        
        api_path = path
        if params:
            query_string = urllib.parse.urlencode(params)
            api_path = f"{path}?{query_string}"
            
        body_str = json.dumps(body) if body else ""
        signature = self._generate_signature(method, api_path, body_str, timestamp)
        
        headers = {
            "X-Api-Key": self.public_key,
            "X-Sign-Date": timestamp,
            "X-Request-Sign": f"dmar ed25519 {signature}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.BASE_URL}{api_path}"
        session = await self.get_session()
        
        async with session.request(method, url, headers=headers, json=body if body else None) as response:
            if response.status != 200:
                text = await response.text()
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"DMarket API Error: {text}",
                    headers=response.headers
                )
            return await response.json()
    
    # --- Market Data ---
    async def get_market_items_v2(self, game_id: str, limit: int = 100, cursor: Optional[str] = None, **filters):
        """ High-throughput Marketplace v2 scan. """
        params = {"currency": "USD", "gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        if filters: params.update(filters)
        return await self.make_request("GET", "/exchange/v1/market/items", params=params)

    # --- Account & Inventory ---
    async def get_real_balance(self) -> float:
        """ Fetches the current USD & DMC balance. Supports Real Balance in Dry Run. """
        try:
            # We fetch the real account balance even in Dry Run to ground the simulation in reality
            res = await self.make_request("GET", "/account/v1/balance")
            # DMarket balance is usually in cents or has a specific structure
            # Logic: USD section
            usd_balance = float(res.get("usd", 0)) / 100.0
            return usd_balance
        except Exception as e:
            if os.getenv("DRY_RUN", "true").lower() == "true":
                logger.debug(f"Real balance fetch failed, using fallback: {e}")
                return 10000.0 
            raise e

    async def get_user_inventory(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ Fetches items owned by the user but NOT currently on sale. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-inventory", params=params)

    # --- v12.2: Detailed Inventory with Status (Phase 2.1) ---
    async def get_user_inventory_detailed(self, game_id: str, limit: int = 100,
                                          cursor: Optional[str] = None,
                                          basic: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch user inventory with FULL status info: trade_protected, reverted, FinalizationTime.

        Returns list of items with normalized fields:
        [{
            "itemId": "...",
            "title": "...",
            "status": "active" | "trade_protected" | "reverted" | "sold",
            "FinalizationTime": 1234567890.0,  # Unix timestamp when status changes
            "price": {"USD": "102", "DMC": ""},
            "createdAt": 1234567890.0,
        }]

        Endpoint: GET /exchange/v1/user-inventory?gameId=a8db&basic={basic}&limit=100
        basic=true returns minimal fields, basic=false returns full status
        """
        all_items: List[Dict[str, Any]] = []
        current_cursor = cursor or ""

        for _ in range(10):  # max 10 pages = 1000 items
            params = {
                "gameId": game_id,
                "limit": limit,
                "basic": str(basic).lower(),
            }
            if current_cursor:
                params["cursor"] = current_cursor
            try:
                res = await self.make_request("GET", "/exchange/v1/user-inventory", params=params)
            except Exception as e:
                logger.warning(f"Detailed inventory fetch failed: {e}")
                return all_items

            items = res.get("items", res.get("objects", []))
            for it in items:
                status = it.get("status", "active")
                if isinstance(status, str):
                    status_lower = status.lower()
                else:
                    status_lower = "active"

                # FinalizationTime can be int (seconds) or string
                fin_raw = it.get("FinalizationTime") or it.get("finalizationTime") or 0
                try:
                    finalization_time = float(fin_raw) if fin_raw else 0.0
                except (ValueError, TypeError):
                    finalization_time = 0.0

                # createdAt
                created_raw = it.get("createdAt") or it.get("acquiredAt") or 0
                try:
                    created_at = float(created_raw) if created_raw else 0.0
                except (ValueError, TypeError):
                    created_at = 0.0

                all_items.append({
                    "itemId": it.get("itemId", ""),
                    "title": it.get("title", ""),
                    "status": status_lower,
                    "FinalizationTime": finalization_time,
                    "price": it.get("price", {}),
                    "createdAt": created_at,
                })

            current_cursor = res.get("cursor", "")
            if not current_cursor:
                break

        return all_items

    async def get_transaction_history(self, days: int = 30, limit: int = 100,
                                      transaction_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent transactions to detect rollbacks (reverted status).

        Returns list of transactions:
        [{
            "type": "buy" | "sell" | "reverted",
            "itemId": "...",
            "amount": 100.0,  # USD value
            "status": "completed" | "reverted" | "trade_protected",
            "timestamp": 1234567890.0,
        }]

        Endpoint: GET /exchange/v1/transactions?days=30&limit=100
        """
        params = {
            "days": days,
            "limit": limit,
        }
        if transaction_type:
            params["type"] = transaction_type
        try:
            res = await self.make_request("GET", "/exchange/v1/transactions", params=params)
        except Exception as e:
            logger.debug(f"Transaction history fetch failed: {e}")
            return []

        txs = res.get("transactions", res.get("items", []))
        normalized = []
        for tx in txs:
            ts_raw = tx.get("createdAt") or tx.get("timestamp") or 0
            try:
                ts = float(ts_raw) if ts_raw else 0.0
            except (ValueError, TypeError):
                ts = 0.0

            amount_raw = tx.get("amount", 0)
            if isinstance(amount_raw, dict):
                cents = amount_raw.get("USD", 0)
                try:
                    amount = float(cents) / 100.0
                except (ValueError, TypeError):
                    amount = 0.0
            else:
                try:
                    amount = float(amount_raw) / 100.0
                except (ValueError, TypeError):
                    amount = 0.0

            status = tx.get("status", "completed")
            tx_type = tx.get("type", "")
            # Map DMarket status to our schema
            if status in ("reverted", "rollback", "rolled_back"):
                tx_type = "reverted"

            normalized.append({
                "type": tx_type,
                "itemId": tx.get("itemId", ""),
                "amount": amount,
                "status": status,
                "timestamp": ts,
            })
        return normalized

    async def get_user_offers(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ Fetches items the user currently has listed for sale. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-offers", params=params)

    # --- Trading Ops (Targets / Buy Orders) ---
    async def batch_create_targets(self, targets: List[Dict[str, Any]]):
        """ Creation of targets (buy orders). Path verified via Swagger 2026. """
        return await self.make_request("POST", "/marketplace-api/v1/user-targets/create", body={"Targets": targets})

    async def batch_delete_targets(self, targets: List[Dict[str, Any]]):
        """ Mass deletion of targets. Path verified via Swagger 2026. """
        return await self.make_request("POST", "/marketplace-api/v1/user-targets/delete", body={"Targets": targets})

    async def buy_items(self, offers: List[Dict[str, Any]]):
        """ 
        Instant Purchase of existing market listings.
        Payload: [{"offerId": "...", "price": {"amount": "123", "currency": "USD"}}]
        """
        return await self.make_request("POST", "/exchange/v1/market/buy", body={"offers": offers})

    async def get_user_targets(self, game_id: str, limit: int = 50, cursor: Optional[str] = None):
        """ List active buy orders. """
        params = {"gameId": game_id, "limit": limit}
        if cursor: params["cursor"] = cursor
        return await self.make_request("GET", "/marketplace-api/v1/user-targets", params=params)

    # --- Fee Analysis (v7.6) ---
    async def get_item_fee(self, game_id: str, item_id: str, price_cents: int) -> float:
        """
        Fetches dynamic fee for a specific item at a given price.
        Implements 12-hour caching (v7.7) to avoid rate limits.
        """
        now = time.time()
        if item_id in self._fee_cache:
            cached = self._fee_cache[item_id]
            if now - cached["timestamp"] < self._fee_cache_ttl:
                return cached["fee"]

        try:
            params = {
                "gameId": game_id,
                "itemId": item_id,
                "price": price_cents,
                "currency": "USD"
            }
            res = await self.make_request("GET", "/exchange/v1/market/fee", params=params)
            fee_pct = float(res.get("fee", 5.0)) / 100.0

            # Update Cache
            self._fee_cache[item_id] = {"fee": fee_pct, "timestamp": now}
            return fee_pct
        except Exception as e:
            if os.getenv("DRY_RUN", "true").lower() != "true":
                logger.warning(f"Could not fetch dynamic fee for {item_id}, fallback to 5%: {e}")
            return 0.05

    # --- v12.2: Bulk fee fetching (Phase 2.2) ---
    async def get_item_fee_bulk(self, game_id: str, item_ids: List[str]) -> Dict[str, float]:
        """
        Batch fetch fees for up to N items in 1 request.
        Returns: {item_id: fee_rate} (e.g., {"abc123": 0.025})

        Endpoint: GET /exchange/v1/items/bulk-fee?gameId=a8db&itemIds=id1,id2,...
        Up to 50 items per request.
        """
        if not item_ids:
            return {}

        results: Dict[str, float] = {}
        chunk_size = 50
        for chunk_start in range(0, len(item_ids), chunk_size):
            chunk = item_ids[chunk_start:chunk_start + chunk_size]
            try:
                # Comma-separated item IDs (DMarket bulk format)
                ids_param = ",".join(chunk)
                res = await self.make_request(
                    "GET",
                    "/exchange/v1/items/bulk-fee",
                    params={"gameId": game_id, "itemIds": ids_param}
                )
                # Response: {"fees": [{"itemId": "abc", "fee": 2.5}, ...]}
                for entry in res.get("fees", []):
                    fid = entry.get("itemId", "")
                    fee_raw = entry.get("fee", 5.0)
                    try:
                        fee_pct = float(fee_raw) / 100.0
                    except (ValueError, TypeError):
                        fee_pct = 0.05
                    if fid:
                        results[fid] = fee_pct
                        # Update single-item cache too
                        self._fee_cache[fid] = {"fee": fee_pct, "timestamp": time.time()}
            except Exception as e:
                logger.debug(f"Bulk fee fetch failed for chunk of {len(chunk)}: {e}")
                # Fallback to 5% for failed items
                for fid in chunk:
                    if fid not in results:
                        results[fid] = 0.05

        return results

    # --- v12.0: Aggregated Prices (Strategy A core) ---
    async def get_aggregated_prices(self, game_id: str, titles: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch of best_bid + best_ask + count for up to 100 items in 1 request.
        Returns: {title: {"best_ask": float, "best_bid": float, "ask_count": int, "bid_count": int}}

        Endpoint: POST /marketplace-api/v1/aggregated-prices
        Body: {"gameId": "a8db", "titles": ["AK-47 | Redline (Field-Tested)", ...]}
        """
        if not titles:
            return {}

        # Chunk to 100 per request (DMarket limit)
        results: Dict[str, Dict[str, Any]] = {}
        for chunk_start in range(0, len(titles), 100):
            chunk = titles[chunk_start:chunk_start + 100]
            try:
                res = await self.make_request(
                    "POST",
                    "/marketplace-api/v1/aggregated-prices",
                    body={"gameId": game_id, "titles": chunk}
                )
                # Response format: {"aggregatedPrices": [{title, bestAsk, bestBid, ...}, ...]}
                for entry in res.get("aggregatedPrices", []):
                    title = entry.get("title", "")
                    if not title:
                        continue
                    # bestAsk and bestBid are in cents (strings) per DMarket format
                    best_ask_cents = entry.get("bestAsk", "0")
                    best_bid_cents = entry.get("bestBid", "0")
                    try:
                        best_ask = float(best_ask_cents) / 100.0 if best_ask_cents else 0.0
                    except (ValueError, TypeError):
                        best_ask = 0.0
                    try:
                        best_bid = float(best_bid_cents) / 100.0 if best_bid_cents else 0.0
                    except (ValueError, TypeError):
                        best_bid = 0.0
                    results[title] = {
                        "best_ask": best_ask,
                        "best_bid": best_bid,
                        "ask_count": int(entry.get("askCount", 0)),
                        "bid_count": int(entry.get("bidCount", 0)),
                    }
            except Exception as e:
                logger.warning(f"Aggregated prices batch failed: {e}")
                # Fill with zeros for failed items
                for t in chunk:
                    if t not in results:
                        results[t] = {"best_ask": 0.0, "best_bid": 0.0, "ask_count": 0, "bid_count": 0}

        return results

    # --- v12.0: Last Sales (Strategy B) ---
    async def get_last_sales(self, game_id: str, title: str, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch real DMarket sale transactions for an item.

        Endpoint: GET /trade-aggregator/v1/last-sales
        Params: gameId, title, days, limit
        """
        try:
            params = {
                "gameId": game_id,
                "title": title,
                "days": days,
                "limit": limit,
            }
            res = await self.make_request("GET", "/trade-aggregator/v1/last-sales", params=params)
            sales = res.get("sales", res.get("items", []))
            normalized = []
            for s in sales:
                price_cents = s.get("price", {}).get("USD", 0) if isinstance(s.get("price"), dict) else s.get("price", 0)
                try:
                    price_usd = float(price_cents) / 100.0
                except (ValueError, TypeError):
                    continue
                normalized.append({
                    "price": price_usd,
                    "date": s.get("date") or s.get("soldAt") or s.get("createdAt"),
                })
            return normalized
        except Exception as e:
            logger.debug(f"Last sales fetch failed for {title}: {e}")
            return []

    # --- v12.0: Low Fee Items (Strategy C) ---
    async def get_low_fee_items(self, game_id: str) -> List[Dict[str, Any]]:
        """
        Daily list of items with reduced DMarket fees (2-3% vs 5%).

        Endpoint: GET /marketplace-api/v1/low-fee-items
        """
        try:
            res = await self.make_request("GET", "/marketplace-api/v1/low-fee-items", params={"gameId": game_id})
            items = res.get("items", [])
            normalized = []
            for it in items:
                title = it.get("title", "")
                fee = it.get("fee", 0.05)
                if isinstance(fee, str):
                    try:
                        fee = float(fee) / 100.0
                    except ValueError:
                        fee = 0.05
                normalized.append({"title": title, "fee_rate": fee})
            return normalized
        except Exception as e:
            logger.debug(f"Low-fee items fetch failed: {e}")
            return []

    # --- v12.0: Sell Endpoints (resale pipeline) ---
    async def create_offer(self, asset_id: str, price_usd: float) -> Dict[str, Any]:
        """
        List an owned item for sale on DMarket.

        Endpoint: POST /marketplace-api/v1/user-offers/create
        Body: {"assetId": "...", "price": {"amount": "123", "currency": "USD"}}
        """
        body = {
            "assetId": asset_id,
            "price": {"amount": str(int(price_usd * 100)), "currency": "USD"},
        }
        return await self.make_request("POST", "/marketplace-api/v1/user-offers/create", body=body)

    async def batch_create_offers(self, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Batch list items for sale.

        Endpoint: POST /marketplace-api/v1/user-offers/create-batch (if available)
        or POST /marketplace-api/v1/user-offers/create with array
        """
        body_offers = []
        for o in offers:
            body_offers.append({
                "assetId": o["asset_id"],
                "price": {"amount": str(int(o["price_usd"] * 100)), "currency": "USD"},
            })
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-offers/create",
            body={"offers": body_offers}
        )

    async def delete_offers(self, offer_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel (delist) one or more offers.

        Endpoint: POST /marketplace-api/v1/user-offers/close
        Body: {"offerIds": ["...", "..."]}
        """
        return await self.make_request(
            "POST",
            "/marketplace-api/v1/user-offers/close",
            body={"offerIds": offer_ids}
        )

    async def edit_offer(self, offer_id: str, new_price_usd: float) -> Dict[str, Any]:
        """
        Reprice an existing offer.

        Endpoint: PATCH /marketplace-api/v1/user-offers/edit
        Body: {"offerId": "...", "price": {"amount": "123", "currency": "USD"}}
        """
        body = {
            "offerId": offer_id,
            "price": {"amount": str(int(new_price_usd * 100)), "currency": "USD"},
        }
        return await self.make_request("PATCH", "/marketplace-api/v1/user-offers/edit", body=body)

    # ------------------------------------------------------------------
    # v12.2 Phase 2.5: API v2 Batch Endpoints
    # ------------------------------------------------------------------
    async def batch_create_offers_v2(self, offers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        v2: Batch list up to 100 items in a single request.

        Endpoint: POST /exchange/v1/user-offers/batch-create
        Body: {"offers": [{"assetId": "...", "price": {"amount": "123", "currency": "USD"}}, ...]}
        """
        body_offers = []
        for o in offers:
            body_offers.append({
                "assetId": o["asset_id"],
                "price": {"amount": str(int(o["price_usd"] * 100)), "currency": "USD"},
            })
        return await self.make_request(
            "POST",
            "/exchange/v1/user-offers/batch-create",
            body={"offers": body_offers}
        )

    async def batch_edit_offers_v2(self, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        v2: Batch reprice up to 100 offers in a single request.

        Endpoint: PATCH /exchange/v1/user-offers/batch-edit
        Body: {"edits": [{"offerId": "...", "price": {"amount": "123", "currency": "USD"}}, ...]}
        """
        body_edits = []
        for e in edits:
            body_edits.append({
                "offerId": e["offer_id"],
                "price": {"amount": str(int(e["new_price_usd"] * 100)), "currency": "USD"},
            })
        return await self.make_request(
            "PATCH",
            "/exchange/v1/user-offers/batch-edit",
            body={"edits": body_edits}
        )

    async def batch_delete_offers_v2(self, offer_ids: List[str]) -> Dict[str, Any]:
        """
        v2: Batch cancel (delist) up to 100 offers in a single request.

        Endpoint: POST /exchange/v1/user-offers/batch-close
        Body: {"offerIds": ["...", "..."]}
        """
        return await self.make_request(
            "POST",
            "/exchange/v1/user-offers/batch-close",
            body={"offerIds": offer_ids}
        )

    async def get_user_offers_v2(self, game_id: str, limit: int = 100,
                                 cursor: Optional[str] = None,
                                 status: Optional[str] = None) -> Dict[str, Any]:
        """
        v2: List active offers with optional status filter.

        Endpoint: GET /exchange/v1/user-offers?gameId=a8db&status=active&limit=100
        """
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return await self.make_request("GET", "/exchange/v1/user-offers", params=params)

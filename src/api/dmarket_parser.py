import json
from typing import Any

import structlog

# v15.2: orjson is 5-10x faster than stdlib json for parsing
try:
    import orjson
    def _loads(s: str | bytes) -> Any:
        return orjson.loads(s)
except ImportError:
    def _loads(s: str | bytes) -> Any:
        return json.loads(s)

try:
    import pandera as pa
    HAS_PANDERA = True
except ImportError:
    HAS_PANDERA = False

# --- Phase 1.1: Rust Integration ---
try:
    import dmarket_parser_rs
    HAS_RUST_PARSER = True
except ImportError:
    HAS_RUST_PARSER = False
# -----------------------------------

logger = structlog.get_logger("DmarketValidator")

class DmarketSkinSchema:
    """Pandera DataFrame schema (skipped if pandera unavailable)."""
    pass

if HAS_PANDERA:
    class DmarketSkinSchemaReal(pa.DataFrameModel):
        item_id: pa.typing.Series[str] = pa.Field(str_matches=r"^[0-9A-Fa-f]+$")
        price_usd: pa.typing.Series[float] = pa.Field(ge=0.01)
        name: pa.typing.Series[str] = pa.Field()

        @pa.check("name", name="prompt_injection_check")
        def sanitize_input(cls, item_names: pa.typing.Series[str]) -> pa.typing.Series[bool]:
            return ~item_names.str.contains(r"[\<\>\{\}\$\`\\]")
    DmarketSkinSchema = DmarketSkinSchemaReal


def parse_aggregated_prices(raw_json: str) -> list[dict[str, Any]]:
    """
    Parse DMarket aggregated-prices response using Rust or Python fallback.

    Input: JSON from POST /marketplace-api/v1/aggregated-prices
    Response format: {"aggregatedPrices": [{title, orderBestPrice, offerBestPrice, ...}, ...]}
    Price amounts are in cents (string or number).

    Returns: [{title, best_ask, best_bid, ask_count, bid_count}, ...]

    Speed: 5-10x faster with Rust (serde + direct PyList construction).
    """
    # UNUSED IN PRODUCTION: market.py never calls this Rust path — see docs/MEMORY.md 'Dead Code Investigation' (2026-08-26). Kept as tested groundwork, not wired into runtime. Do not assume this executes.
    if HAS_RUST_PARSER:
        try:
            return list(dmarket_parser_rs.parse_aggregated_prices_rs(raw_json))
        except Exception as e:
            logger.warning(f"Rust Aggregated Prices parser failed: {e}", exc_info=True)

    # Python fallback
    result: list[dict[str, Any]] = []
    try:
        data = _loads(raw_json)
        entries = data.get("aggregatedPrices", [])
        for entry in entries:
            title = entry.get("title", "")
            # DMarket API: orderBestPrice = best BUY order = BID
            #            offerBestPrice = best SELL offer = ASK
            bid_obj = entry.get("orderBestPrice") or {}
            ask_obj = entry.get("offerBestPrice") or {}
            bid_amount = bid_obj.get("Amount", "0")
            ask_amount = ask_obj.get("Amount", "0")

            try:
                best_bid = float(bid_amount) / 100.0
            except (ValueError, TypeError):
                best_bid = 0.0

            try:
                best_ask = float(ask_amount) / 100.0
            except (ValueError, TypeError):
                best_ask = 0.0

            try:
                bid_count = int(entry.get("orderCount", 0))
            except (ValueError, TypeError):
                bid_count = 0
            try:
                ask_count = int(entry.get("offerCount", 0))
            except (ValueError, TypeError):
                ask_count = 0
            result.append({
                "title": title,
                "best_ask": best_ask,
                "best_bid": best_bid,
                "ask_count": ask_count,
                "bid_count": bid_count,
            })
    except Exception as e:
        logger.error(f"Aggregated prices parse error: {e}")
        return []

    return result


def parse_aggregated_prices_from_dict(data: dict) -> list[dict[str, Any]]:
    """
    Parse aggregated-prices from an already-deserialized Python dict.
    Falls back to Python parsing (no Rust re-serialization overhead).
    """
    result: list[dict[str, Any]] = []
    try:
        entries = data.get("aggregatedPrices", [])
        for entry in entries:
            title = entry.get("title", "")
            bid_obj = entry.get("orderBestPrice") or {}
            ask_obj = entry.get("offerBestPrice") or {}
            bid_amount = bid_obj.get("Amount", "0")
            ask_amount = ask_obj.get("Amount", "0")
            try:
                best_bid = float(bid_amount) / 100.0
            except (ValueError, TypeError):
                best_bid = 0.0
            try:
                best_ask = float(ask_amount) / 100.0
            except (ValueError, TypeError):
                best_ask = 0.0
            try:
                bid_count = int(entry.get("orderCount", 0))
            except (ValueError, TypeError):
                bid_count = 0
            try:
                ask_count = int(entry.get("offerCount", 0))
            except (ValueError, TypeError):
                ask_count = 0
            result.append({
                "title": title,
                "best_ask": best_ask,
                "best_bid": best_bid,
                "ask_count": ask_count,
                "bid_count": bid_count,
            })
    except Exception as e:
        logger.error(f"Aggregated prices parse (dict) error: {e}")
        return []

    return result

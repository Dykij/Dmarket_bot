import json
import re
import structlog
from typing import Annotated, Optional
import pandera as pa
from pydantic import BaseModel, root_validator, Field

# --- Phase 1.1: Rust Integration ---
try:
    import dmarket_parser_rs
    HAS_RUST_PARSER = True
except ImportError:
    HAS_RUST_PARSER = False
# -----------------------------------

logger = structlog.get_logger("DmarketValidator")

class DmarketSkinSchema(pa.SchemaModel):
    item_id: pa.typing.Series[str] = pa.Field(str_matches=r"^[0-9A-Fa-f]+$")
    price_usd: pa.typing.Series[float] = pa.Field(ge=0.01)
    name: pa.typing.Series[str] = pa.Field(allow_duplicates=True)
    
    @pa.check("name", name="prompt_injection_check")
    def sanitize_input(cls, item_names: pa.typing.Series[str]) -> pa.typing.Series[bool]:
        """Prompt Injection sanitization. Ensures no system commands or escape chars inside the skin name."""
        return item_names.str.contains(r"[\<\>\{\}\$\`\\]") == False

class ParsedSkinData(BaseModel):
    item_id: str = Field(description="DMarket Skin Unique ID")
    price_usd: float = Field(description="Price in USD")
    name: str = Field(description="Skin Name")
    
    @root_validator(pre=True)
    def injection_protection(cls, values):
        """Pre-validation sanitizer for Prompt Injection"""
        name = values.get("name", "")
        # Remove potentially malicious characters from string inputs
        sanitized = re.sub(r'[\<\>\{\}\$\`\\]', '', name)
        values["name"] = sanitized
        return values
        return values

def validate_batch_response(raw_json: str):
    """
    Parses a batch marketplace response using Rust (high speed) or Python fallback.
    """
    if HAS_RUST_PARSER:
        try:
            return dmarket_parser_rs.parse_market_response_rs(raw_json)
        except Exception as e:
            logger.warning(f"Rust Batch Parser failed: {e}")

    # Python Fallback
    try:
        data = json.loads(raw_json)
        objects = data.get("objects", [])
        return [ParsedSkinData(**item) for item in objects]
    except Exception as e:
        logger.error(f"Batch Validation Error: {e}")
        return []

def validate_dmarket_response(raw_json: str):
    """
    Validates single API data from DMarket strictly via Rust (if available)
    or Pydantic fallback.
    """
    # Try high-performance Rust parser first
    if HAS_RUST_PARSER:
        try:
            rust_data = dmarket_parser_rs.validate_dmarket_response_rs(raw_json)
            return rust_data
        except Exception as e:
            logger.warning(f"Rust Parser failed, falling back to Python: {e}")

    # Fallback to Python implementation
    try:
        data = json.loads(raw_json)
        # Using Pydantic for object level parsing
        parsed_data = ParsedSkinData(**data)
        return parsed_data
    except Exception as e:
        logger.error(f"Data Validation Error: {e}")
        return None

if __name__ == "__main__":
    test_payload = '{"item_id": "A1B2C3", "price_usd": 12.50, "name": "AK-47 <system>rm -rf</system>"}'
    print(f"Using Rust Parser: {HAS_RUST_PARSER}")
    print("Testing payload with Prompt Injection attempt:")
    print(validate_dmarket_response(test_payload))

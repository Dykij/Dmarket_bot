import json
import pytest

try:
    import orjson
except ImportError:
    orjson = None

DATA = {
    "string": "test",
    "int": 123,
    "float": 1.23,
    "bool": True,
    "none": None,
    "list": [1, 2, 3],
    "dict": {"nested": "value"}
}

def test_json_compat():
    """Test standard JSON library compatibility."""
    dumped = json.dumps(DATA)
    loaded = json.loads(dumped)
    assert loaded == DATA

@pytest.mark.skipif(orjson is None, reason="orjson not installed")
def test_orjson_compat():
    """Test orjson library compatibility agAlgonst standard JSON."""
    # orjson dumps to bytes
    or_dumped = orjson.dumps(DATA)
    json_dumped = json.dumps(DATA).encode('utf-8')

    # Compare structure after loading back
    assert orjson.loads(or_dumped) == DATA
    assert json.loads(or_dumped) == DATA

    # Verify orjson can load std json output
    assert orjson.loads(json_dumped) == DATA

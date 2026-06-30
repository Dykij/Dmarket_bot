"""
test_model_selector.py — QA: Model selector validation for NVIDIA NIM Orchestrator.

Verifies that:
  1. Model groups map correctly to task categories
  2. API keys from NVIDIA_NGC_KEYS bind to correct endpoint groups
  3. Config schema validation passes (no OmniRoute artifacts)
  4. Model selection from opencode.json matches .env pool
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def opencode_config() -> dict:
    """Load project opencode.json."""
    path = PROJECT_ROOT / "opencode.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def env_vars() -> dict:
    """Parse NIM-related env vars from .env."""
    env_path = PROJECT_ROOT / ".env"
    vars_dict: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key.startswith(("NIM_", "NVIDIA_NIM", "NVIDIA_NGC")):
                    vars_dict[key] = value
    return vars_dict


class TestOpencodeSchema:
    """Validate opencode.json structure after OmniRoute removal."""

    def test_no_omniroute_in_provider(self, opencode_config):
        """OmniRoute must not appear in the provider section."""
        providers = opencode_config.get("provider", {})
        assert "omniroute" not in providers
        assert "OmniRoute" not in providers

    def test_no_omniroute_in_model_keys(self, opencode_config):
        """Model and small_model keys must not reference omniroute."""
        model = opencode_config.get("model", "")
        small_model = opencode_config.get("small_model", "")
        assert "omniroute" not in model, f"model key contains omniroute: {model}"
        assert "omniroute" not in small_model, f"small_model contains omniroute: {small_model}"

    def test_nvidia_nim_provider_exists(self, opencode_config):
        """NVIDIA NIM provider must be present."""
        providers = opencode_config.get("provider", {})
        assert "nvidia-nim" in providers
        nim_config = providers["nvidia-nim"]
        assert nim_config["options"]["baseURL"] == "https://integrate.api.nvidia.com/v1"

    def test_all_model_groups_present(self, opencode_config):
        """All three task groups must have models defined."""
        models = opencode_config.get("provider", {}).get("nvidia-nim", {}).get("models", {})
        groups_found = set()
        for model_id, model_def in models.items():
            groups_found.add(model_def.get("group", ""))

        assert "multimodal-flagship" in groups_found
        assert "reasoning-layer" in groups_found
        assert "architectural-coding" in groups_found

    def test_default_model_is_heavy(self, opencode_config):
        """Default model must be from the architectural-coding group."""
        model_key = opencode_config.get("model", "")
        models = opencode_config.get("provider", {}).get("nvidia-nim", {}).get("models", {})
        model_id = model_key.replace("nvidia-nim/", "")

        assert model_id in models, f"Model {model_id} not in registered models"
        model_def = models[model_id]
        assert model_def.get("group") == "architectural-coding", (
            f"Default model {model_id} group is {model_def.get('group')}, expected architectural-coding"
        )

    def test_small_model_is_fast_coding(self, opencode_config):
        """Small model must be from the reasoning-layer group."""
        small_model_key = opencode_config.get("small_model", "")
        models = opencode_config.get("provider", {}).get("nvidia-nim", {}).get("models", {})
        model_id = small_model_key.replace("nvidia-nim/", "")

        assert model_id in models, f"Small model {model_id} not in registered models"
        model_def = models[model_id]
        assert model_def.get("group") == "reasoning-layer", (
            f"Small model {model_id} group is {model_def.get('group')}, expected reasoning-layer"
        )

    def test_context_limits_set(self, opencode_config):
        """Every model must have valid context and output limits."""
        models = opencode_config.get("provider", {}).get("nvidia-nim", {}).get("models", {})
        for model_id, model_def in models.items():
            limit = model_def.get("limit", {})
            assert "context" in limit, f"Model {model_id} missing context limit"
            assert limit["context"] > 0, f"Model {model_id} context is 0"
            assert "output" in limit, f"Model {model_id} missing output limit"
            assert limit["output"] > 0, f"Model {model_id} output is 0"

    def test_code_specialized_model_has_code_group(self, opencode_config):
        """Qwen 3.5 397B must be in architectural-coding group."""
        models = opencode_config.get("provider", {}).get("nvidia-nim", {}).get("models", {})
        qwen = models.get("qwen/qwen3.5-397b-a17b")
        assert qwen is not None, "Qwen 3.5 397B missing from models"
        assert qwen["group"] == "architectural-coding"
        assert qwen["name"] == "Qwen 3.5 397B (Архитектурный кодинг)"


class TestModelApiKeyBinding:
    """Verify model groups bind correctly to API key pools."""

    def test_env_api_keys_parse_correctly(self, env_vars):
        """NVIDIA_NGC_KEYS must be a valid JSON array or CSV list."""
        raw = env_vars.get("NVIDIA_NGC_KEYS", "[]")

        try:
            keys = json.loads(raw)
            assert isinstance(keys, list)
            assert len(keys) > 0
        except json.JSONDecodeError:
            keys = [k.strip().strip("'\"") for k in raw.split(",") if k.strip()]
            assert len(keys) > 0, f"No API keys parsed from: {raw}"

        for key in keys:
            assert len(key) > 10, f"API key too short: {key}"

    def test_pool_models_match_opencode_config(self, opencode_config, env_vars):
        """Models referenced in .env pools must exist in opencode.json."""
        models = opencode_config.get("provider", {}).get("nvidia-nim", {}).get("models", {})
        registered_ids = set(models.keys())

        heavy = env_vars.get("NIM_POOL_HEAVY_REASONING", "")
        fast = env_vars.get("NIM_POOL_FAST_CODING", "")
        code = env_vars.get("NIM_POOL_CODE_SPECIALIZED", "")

        all_pool_ids = set()
        for pool in [heavy, fast, code]:
            if pool:
                for mid in pool.split(","):
                    mid = mid.strip()
                    if mid:
                        all_pool_ids.add(mid)

        for pool_id in all_pool_ids:
            assert pool_id in registered_ids, (
                f"Pool model '{pool_id}' is NOT registered in opencode.json models"
            )

    def test_nim_enabled_default_true(self, env_vars):
        """NIM orchestrator must be enabled by default."""
        enabled = env_vars.get("NVIDIA_NIM_ENABLED", "true")
        assert enabled.lower() == "true"

    def test_router_strategy_valid(self, env_vars):
        """NIM_ROUTER_STRATEGY must be a valid value."""
        strategy = env_vars.get("NIM_ROUTER_STRATEGY", "RoundRobin")
        assert strategy in ("RoundRobin", "LeastConnections", "WeightedPick")

    def test_timeout_values_valid(self, env_vars):
        """Timeout values must be positive integers."""
        cooldown = env_vars.get("NIM_CIRCUIT_BREAKER_COOLDOWN_MS", "0")
        timeout = env_vars.get("NIM_REQUEST_TIMEOUT_MS", "0")

        try:
            cooldown_int = int(cooldown)
            timeout_int = int(timeout)
            assert cooldown_int >= 1000, f"Cooldown too low: {cooldown_int}ms"
            assert timeout_int >= 30000, f"Timeout too low: {timeout_int}ms"
        except (ValueError, TypeError) as e:
            pytest.fail(f"Invalid timeout value: {e}")

    def test_max_retries_is_four(self, env_vars):
        """NIM_MAX_RETRIES must be 4 (user-specified requirement)."""
        max_retries = env_vars.get("NIM_MAX_RETRIES", "0")
        assert int(max_retries) == 4, f"Expected NIM_MAX_RETRIES=4, got {max_retries}"
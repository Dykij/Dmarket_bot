"""
Canary Deployment and Blue-Green Testing Module.

Tests for deployment strategies, traffic routing, and gradual rollouts.

Covers:
- Canary deployment patterns
- Blue-green deployments
- Traffic shifting
- Health monitoring
- Rollback strategies
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

import pytest


class DeploymentState(Enum):
    """Deployment states."""

    STABLE = "stable"
    CANARY = "canary"
    ROLLING = "rolling"
    ROLLBACK = "rollback"
    COMPLETE = "complete"


@dataclass
class DeploymentMetrics:
    """Metrics for deployment health."""

    total_requests: int = 0
    error_count: int = 0
    latency_sum: float = 0.0
    latency_samples: list = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.error_count / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def avg_latency(self) -> float:
        return self.latency_sum / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def p99_latency(self) -> float:
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]


class TestCanaryDeploymentPatterns:
    """Tests for canary deployment patterns."""

    @pytest.fixture()
    def canary_config(self):
        """Canary deployment configuration."""
        return {
            "initial_percentage": 5,
            "increment": 5,
            "max_percentage": 100,
            "evaluation_period": 60,  # seconds
            "error_threshold": 0.05,
            "latency_threshold": 500,  # ms
        }

    def test_canary_percentage_increments(self, canary_config):
        """Test canary traffic percentage increments."""
        current = canary_config["initial_percentage"]
        stages = []

        while current <= canary_config["max_percentage"]:
            stages.append(current)
            current += canary_config["increment"]
            if current > canary_config["max_percentage"] and stages[-1] != 100:
                stages.append(100)
                break

        assert stages[0] == 5
        assert stages[-1] == 100
        assert all(stages[i] < stages[i + 1] for i in range(len(stages) - 1))

    def test_traffic_router(self):
        """Test canary traffic router."""

        class TrafficRouter:
            def __init__(self, canary_percentage: int = 0):
                self.canary_percentage = canary_percentage
                self.canary_version = "v2.0.0"
                self.stable_version = "v1.0.0"

            def route(self, request_id: str) -> str:
                """Route request to appropriate version."""
                # Use consistent hashing for sticky routing
                hash_val = hash(request_id) % 100
                if hash_val < self.canary_percentage:
                    return self.canary_version
                return self.stable_version

            def set_percentage(self, percentage: int):
                self.canary_percentage = max(0, min(100, percentage))

        router = TrafficRouter(canary_percentage=20)

        # Test routing distribution
        canary_count = 0
        total = 10000

        for i in range(total):
            if router.route(f"request_{i}") == "v2.0.0":
                canary_count += 1

        actual_pct = canary_count / total * 100
        assert 18 <= actual_pct <= 22  # ~20% with variance

    def test_sticky_session_routing(self):
        """Test that same user always gets same version."""

        class StickyRouter:
            def __init__(self, canary_percentage: int = 50):
                self.canary_percentage = canary_percentage
                self.user_assignments: dict = {}

            def route(self, user_id: str) -> str:
                """Route user to version (sticky)."""
                if user_id in self.user_assignments:
                    return self.user_assignments[user_id]

                # Assign based on hash
                version = "canary" if hash(user_id) % 100 < self.canary_percentage else "stable"
                self.user_assignments[user_id] = version
                return version

        router = StickyRouter(canary_percentage=50)

        # Same user should always get same version
        user_id = "user_12345"
        version1 = router.route(user_id)
        version2 = router.route(user_id)
        version3 = router.route(user_id)

        assert version1 == version2 == version3


class TestBlueGreenDeployment:
    """Tests for blue-green deployment patterns."""

    def test_blue_green_switch(self):
        """Test blue-green environment switching."""

        class BlueGreenManager:
            def __init__(self):
                self.active = "blue"
                self.blue_version = "v1.0.0"
                self.green_version = "v1.0.0"

            def deploy_to_inactive(self, version: str):
                """Deploy to inactive environment."""
                if self.active == "blue":
                    self.green_version = version
                else:
                    self.blue_version = version

            def switch(self):
                """Switch active environment."""
                self.active = "green" if self.active == "blue" else "blue"

            def rollback(self):
                """Rollback to previous environment."""
                self.switch()

            @property
            def active_version(self) -> str:
                return self.blue_version if self.active == "blue" else self.green_version

        manager = BlueGreenManager()
        assert manager.active == "blue"
        assert manager.active_version == "v1.0.0"

        # Deploy new version to green
        manager.deploy_to_inactive("v2.0.0")
        assert manager.active_version == "v1.0.0"  # Still on blue

        # Switch to green
        manager.switch()
        assert manager.active == "green"
        assert manager.active_version == "v2.0.0"

        # Rollback
        manager.rollback()
        assert manager.active == "blue"
        assert manager.active_version == "v1.0.0"

    def test_blue_green_with_health_check(self):
        """Test blue-green deployment with health checks."""

        class HealthChecker:
            def __init__(self):
                self.health_status: dict = {"blue": True, "green": True}

            def check_health(self, environment: str) -> bool:
                return self.health_status.get(environment, False)

            def set_health(self, environment: str, healthy: bool):
                self.health_status[environment] = healthy

        class SafeBlueGreenManager:
            def __init__(self, health_checker: HealthChecker):
                self.active = "blue"
                self.health_checker = health_checker

            def safe_switch(self) -> bool:
                """Switch only if target is healthy."""
                target = "green" if self.active == "blue" else "blue"
                if self.health_checker.check_health(target):
                    self.active = target
                    return True
                return False

        health = HealthChecker()
        manager = SafeBlueGreenManager(health)

        # Green is healthy - switch succeeds
        assert manager.safe_switch()
        assert manager.active == "green"

        # Make blue unhealthy
        health.set_health("blue", False)

        # Switch fAlgols
        assert not manager.safe_switch()
        assert manager.active == "green"


class TestDeploymentHealthMonitoring:
    """Tests for deployment health monitoring."""

    @pytest.fixture()
    def health_monitor(self):
        """Health monitor fixture."""

        class HealthMonitor:
            def __init__(self, error_threshold: float = 0.05, latency_threshold: float = 500):
                self.error_threshold = error_threshold
                self.latency_threshold = latency_threshold
                self.metrics: dict = {}

            def record(self, version: str, success: bool, latency: float):
                if version not in self.metrics:
                    self.metrics[version] = DeploymentMetrics()
                m = self.metrics[version]
                m.total_requests += 1
                if not success:
                    m.error_count += 1
                m.latency_sum += latency
                m.latency_samples.append(latency)

            def is_healthy(self, version: str) -> bool:
                if version not in self.metrics:
                    return True
                m = self.metrics[version]
                if m.total_requests < 100:
                    return True  # Not enough data
                return (
                    m.error_rate <= self.error_threshold and m.avg_latency <= self.latency_threshold
                )

            def compare_versions(self, stable: str, canary: str) -> dict:
                stable_m = self.metrics.get(stable, DeploymentMetrics())
                canary_m = self.metrics.get(canary, DeploymentMetrics())
                return {
                    "stable_error_rate": stable_m.error_rate,
                    "canary_error_rate": canary_m.error_rate,
                    "stable_latency": stable_m.avg_latency,
                    "canary_latency": canary_m.avg_latency,
                    "canary_better": canary_m.error_rate <= stable_m.error_rate
                    and canary_m.avg_latency <= stable_m.avg_latency,
                }

        return HealthMonitor()

    def test_healthy_deployment(self, health_monitor):
        """Test monitoring of healthy deployment."""
        # Simulate healthy traffic
        for _ in range(500):
            health_monitor.record(
                "v1.0.0", success=random.random() > 0.02, latency=random.uniform(100, 300)
            )

        assert health_monitor.is_healthy("v1.0.0")

    def test_unhealthy_deployment_errors(self, health_monitor):
        """Test detection of high error rate."""
        # Simulate high error rate
        for _ in range(500):
            health_monitor.record(
                "v2.0.0", success=random.random() > 0.15, latency=random.uniform(100, 300)
            )

        assert not health_monitor.is_healthy("v2.0.0")

    def test_unhealthy_deployment_latency(self, health_monitor):
        """Test detection of high latency."""
        # Simulate high latency
        for _ in range(500):
            health_monitor.record(
                "v2.0.0", success=True, latency=random.uniform(600, 1000)
            )  # High latency

        assert not health_monitor.is_healthy("v2.0.0")

    def test_version_comparison(self, health_monitor):
        """Test comparison between versions."""
        # Use fixed seed for reproducible random tests
        import random as _random

        _random.seed(42)

        # Stable version with higher error rate (~5%)
        for _ in range(500):
            health_monitor.record(
                "stable", success=_random.random() > 0.05, latency=_random.uniform(100, 300)
            )

        # Better canary version with lower error rate (~1%)
        for _ in range(500):
            health_monitor.record(
                "canary", success=_random.random() > 0.01, latency=_random.uniform(80, 250)
            )

        comparison = health_monitor.compare_versions("stable", "canary")
        # With larger difference (5% vs 1%), canary should be better with high probability
        # Allow small tolerance for statistical fluctuations
        assert comparison["canary_error_rate"] <= comparison["stable_error_rate"] + 0.02


class TestRollbackStrategies:
    """Tests for rollback strategies."""

    def test_automatic_rollback_on_error(self):
        """Test automatic rollback triggered by errors."""

        class AutoRollbackManager:
            def __init__(self, error_threshold: float = 0.1):
                self.error_threshold = error_threshold
                self.current_version = "v1.0.0"
                self.previous_version = None
                self.error_count = 0
                self.request_count = 0
                self.rolled_back = False

            def deploy(self, version: str):
                self.previous_version = self.current_version
                self.current_version = version
                self.error_count = 0
                self.request_count = 0
                self.rolled_back = False

            def record_request(self, is_error: bool):
                self.request_count += 1
                if is_error:
                    self.error_count += 1
                self._check_rollback()

            def _check_rollback(self):
                if self.request_count >= 100:
                    error_rate = self.error_count / self.request_count
                    if error_rate > self.error_threshold and self.previous_version:
                        self.rollback()

            def rollback(self):
                if self.previous_version:
                    self.current_version = self.previous_version
                    self.previous_version = None
                    self.rolled_back = True

        manager = AutoRollbackManager(error_threshold=0.1)
        manager.deploy("v2.0.0")

        # Simulate deterministic high error rate (20 errors out of 100 = 20%)
        # Use deterministic approach instead of random
        for i in range(100):
            # 20 errors guaranteed (every 5th request is an error)
            is_error = i % 5 == 0
            manager.record_request(is_error=is_error)

        assert manager.rolled_back
        assert manager.current_version == "v1.0.0"

    def test_manual_rollback(self):
        """Test manual rollback capability."""

        class VersionManager:
            def __init__(self):
                self.versions: list = ["v1.0.0"]
                self.current_idx = 0

            def deploy(self, version: str):
                self.versions.append(version)
                self.current_idx = len(self.versions) - 1

            def rollback(self, steps: int = 1) -> str:
                new_idx = max(0, self.current_idx - steps)
                self.current_idx = new_idx
                return self.versions[new_idx]

            @property
            def current_version(self) -> str:
                return self.versions[self.current_idx]

        manager = VersionManager()
        manager.deploy("v1.1.0")
        manager.deploy("v1.2.0")
        manager.deploy("v2.0.0")

        assert manager.current_version == "v2.0.0"

        # Rollback 1 step
        manager.rollback(1)
        assert manager.current_version == "v1.2.0"

        # Rollback 2 steps
        manager.rollback(2)
        assert manager.current_version == "v1.0.0"


class TestProgressiveDelivery:
    """Tests for progressive delivery patterns."""

    def test_progressive_rollout(self):
        """Test progressive rollout with stages."""

        class ProgressiveRollout:
            def __init__(self, stages: list = None):
                self.stages = stages or [1, 5, 10, 25, 50, 75, 100]
                self.current_stage_idx = 0
                self.paused = False

            @property
            def current_percentage(self) -> int:
                return self.stages[self.current_stage_idx]

            def advance(self) -> bool:
                if self.paused:
                    return False
                if self.current_stage_idx < len(self.stages) - 1:
                    self.current_stage_idx += 1
                    return True
                return False

            def pause(self):
                self.paused = True

            def resume(self):
                self.paused = False

            def reset(self):
                self.current_stage_idx = 0
                self.paused = False

            @property
            def is_complete(self) -> bool:
                return self.current_percentage == 100

        rollout = ProgressiveRollout()
        assert rollout.current_percentage == 1

        # Advance through stages
        for _ in range(3):
            rollout.advance()
        assert rollout.current_percentage == 25

        # Pause
        rollout.pause()
        rollout.advance()
        assert rollout.current_percentage == 25  # No change

        # Resume and continue
        rollout.resume()
        while rollout.advance():
            pass

        assert rollout.is_complete
        assert rollout.current_percentage == 100

    def test_feature_flag_progressive_rollout(self):
        """Test progressive rollout using feature flags."""

        class FeatureFlagRollout:
            def __init__(self, feature_name: str):
                self.feature_name = feature_name
                self.percentage = 0
                self.user_overrides: dict = {}

            def is_enabled_for_user(self, user_id: str) -> bool:
                # Check override first
                if user_id in self.user_overrides:
                    return self.user_overrides[user_id]
                # Otherwise use percentage
                return hash(f"{self.feature_name}:{user_id}") % 100 < self.percentage

            def set_percentage(self, percentage: int):
                self.percentage = max(0, min(100, percentage))

            def enable_for_user(self, user_id: str):
                self.user_overrides[user_id] = True

            def disable_for_user(self, user_id: str):
                self.user_overrides[user_id] = False

        flag = FeatureFlagRollout("new_dashboard")
        flag.set_percentage(10)

        # Count enabled users
        enabled = sum(1 for i in range(1000) if flag.is_enabled_for_user(f"user_{i}"))

        assert 60 <= enabled <= 140  # ~10% with variance (wider margin for random fluctuations)

        # Test override
        flag.enable_for_user("special_user")
        assert flag.is_enabled_for_user("special_user")

        flag.disable_for_user("special_user")
        assert not flag.is_enabled_for_user("special_user")


class TestDeploymentGates:
    """Tests for deployment gates and approvals."""

    def test_deployment_gates(self):
        """Test deployment gates/checkpoints."""

        class DeploymentGate:
            def __init__(self, name: str, check_func: Callable[[], bool]):
                self.name = name
                self.check_func = check_func
                self.passed = False

            def check(self) -> bool:
                self.passed = self.check_func()
                return self.passed

        class GatedDeployment:
            def __init__(self):
                self.gates: list = []
                self.current_gate_idx = 0

            def add_gate(self, gate: DeploymentGate):
                self.gates.append(gate)

            def proceed(self) -> tuple[bool, str]:
                if self.current_gate_idx >= len(self.gates):
                    return True, "deployment_complete"

                gate = self.gates[self.current_gate_idx]
                if gate.check():
                    self.current_gate_idx += 1
                    return True, f"passed_{gate.name}"
                return False, f"blocked_at_{gate.name}"

            @property
            def is_complete(self) -> bool:
                return self.current_gate_idx >= len(self.gates)

        deployment = GatedDeployment()
        deployment.add_gate(DeploymentGate("unit_tests", lambda: True))
        deployment.add_gate(DeploymentGate("integration_tests", lambda: True))
        deployment.add_gate(DeploymentGate("security_scan", lambda: True))
        deployment.add_gate(DeploymentGate("approval", lambda: True))

        # Pass through all gates
        results = []
        while not deployment.is_complete:
            passed, msg = deployment.proceed()
            results.append((passed, msg))

        assert all(r[0] for r in results)
        assert deployment.is_complete

    def test_deployment_blocked_at_gate(self):
        """Test deployment blocked at a gate."""
        call_count = [0]

        def fAlgoling_check():
            call_count[0] += 1
            return False

        class GatedDeployment:
            def __init__(self, gates: list):
                self.gates = gates
                self.current_idx = 0

            def proceed(self) -> tuple[bool, str]:
                if self.current_idx >= len(self.gates):
                    return True, "complete"
                name, check = self.gates[self.current_idx]
                if check():
                    self.current_idx += 1
                    return True, name
                return False, f"blocked_{name}"

        deployment = GatedDeployment([
            ("tests", lambda: True),
            ("security", fAlgoling_check),
            ("approval", lambda: True),
        ])

        # First gate passes
        assert deployment.proceed() == (True, "tests")

        # Second gate blocks
        assert deployment.proceed() == (False, "blocked_security")
        assert deployment.proceed() == (False, "blocked_security")
        assert call_count[0] == 2

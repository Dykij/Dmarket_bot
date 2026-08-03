"""
Reachability-audit: verification that key methods are actually called from the trading cycle.
"""
import ast
from pathlib import Path


def test_evaluate_trade_size_is_called():
    """P1: DynamicRiskManager.evaluate_trade_size must be called from execution.py"""
    execution_path = Path("src/core/target_sniping/execution.py")
    content = execution_path.read_text()

    # Check method exists in code
    assert "evaluate_trade_size" in content, "evaluate_trade_size not found in execution.py"

    # AST check: there must be ast.Call to evaluate_trade_size
    tree = ast.parse(content)
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "evaluate_trade_size"
    ]
    assert len(calls) >= 1, f"evaluate_trade_size() not called from execution.py (found {len(calls)} calls)"


def test_calculate_demand_score_dedup():
    """P2: calculate_demand_score should use cache when available."""
    orchestrator_path = Path("src/core/target_sniping/cycle_orchestrator.py")
    content = orchestrator_path.read_text()

    # Check that _scores_cache is used
    assert "_scores_cache" in content, "_scores_cache not found in cycle_orchestrator.py"

    # Check that _scores_cache is populated from demand_opps
    assert '_scores_cache: dict[str, dict] = {opp["title"]: opp for opp in demand_opps}' in content

    # Count direct calls to calculate_demand_score in orchestrator
    tree = ast.parse(content)
    direct_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "calculate_demand_score"
    ]
    # 2 legitimate calls: wear-expansion (new variants) + diversity (new items)
    # Both evaluate items NOT in _scores_cache (new items not scored by is_demand_opportunity)
    assert len(direct_calls) <= 2, f"Too many direct calls to calculate_demand_score: {len(direct_calls)}"


def test_find_demand_opportunities_removed():
    """P3: find_demand_opportunities must be removed"""
    src_files = list(Path("src").rglob("*.py"))
    for f in src_files:
        if "__pycache__" in str(f):
            continue
        content = f.read_text()
        assert "find_demand_opportunities" not in content, f"{f} contains find_demand_opportunities"


def test_profit_tracker_wiring():
    """Verify ProfitTracker is wired into execution.py and resale_prod.py"""
    execution = Path("src/core/target_sniping/execution.py").read_text()
    resale = Path("src/core/target_sniping/resale_prod.py").read_text()
    assert "record_buy" in execution, "record_buy not found in execution.py"
    assert "record_sell" in resale, "record_sell not found in resale_prod.py"


def test_dynamic_risk_import():
    """P1: DynamicRiskManager must be imported in execution.py"""
    execution = Path("src/core/target_sniping/execution.py").read_text()
    assert "from src.risk.dynamic_manager import DynamicRiskManager" in execution

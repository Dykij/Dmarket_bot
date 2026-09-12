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

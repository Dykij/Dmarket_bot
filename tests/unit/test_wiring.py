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


def test_demand_strategy_reachability():
    """P3b: Every public def in demand_strategy.py must have ≥1 call in src/."""
    strategy_path = Path("src/core/target_sniping/demand_strategy.py")
    strategy_content = strategy_path.read_text()
    tree = ast.parse(strategy_content)

    # Collect all public function definitions (not starting with _)
    public_defs = [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]
    assert len(public_defs) > 0, "No public functions found in demand_strategy.py"

    # Search for calls to each public def across ALL src/*.py files (including self)
    src_files = [f for f in Path("src").rglob("*.py") if "__pycache__" not in str(f)]
    unreachable = []
    for func_name in public_defs:
        found = False
        for f in src_files:
            content = f.read_text()
            if func_name in content:
                # Verify it's a call, not just a comment or string
                try:
                    ftree = ast.parse(content)
                    for node in ast.walk(ftree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == func_name:
                                found = True
                                break
                            if isinstance(node.func, ast.Attribute) and node.func.attr == func_name:
                                found = True
                                break
                except SyntaxError:
                    pass  # Skip files with syntax errors
            if found:
                break
        if not found:
            unreachable.append(func_name)

    # Known dead code (documented in DEAD_CODE_INTEGRATION_PLAN.md)
    # These are kept for future use but currently have zero callers
    KNOWN_DEAD = {"clear_obi_history"}  # Utility function, no callers yet
    truly_unreachable = [f for f in unreachable if f not in KNOWN_DEAD]

    assert not truly_unreachable, f"Unreachable public functions in demand_strategy.py: {truly_unreachable}"


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

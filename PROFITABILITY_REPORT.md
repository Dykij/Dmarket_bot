# Strategy Profitability Report (v14.4)

## Simulation Metadata
- **Mode**: Sandbox (Dry Run)
- **Strategy**: Balance-Aware Target Sniping v14.4
- **Oracle**: CS2Cap (41 marketplaces) + DMarket aggregated prices
- **Balance Gate**: max($5.00, effective_balance × 0.10), reserve=$10
- **Kelly**: Half Kelly (0.50), drawdown freeze at 15%

## Observations
Check `logs/bot_24_7.log` for cycle logs. Run `python tests/sandbox_full_cycle.py` for the latest v14.4 balance-aware simulation with Affordable/Missed report.

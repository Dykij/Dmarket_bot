# Project Memory (MEMORY.md)

## Current State & Recent Accomplishments
- **Oracle Removal:** Fully removed external oracles (Market.CSGO, Waxpeer, CSFloat, Steam). Strategy now exclusively depends on DMarket API.
- **filter.py Fix:** Replaced oracle validation with DMarket `agg_prices`.
- **has_reference_discount:** Diagnosed as tautological (cs_price always 0 post-oracle-removal, condition always False). Definition and all 3 usages REMOVED in commit 21e489a on feature/remove-oracles-formula-audit. Not merged to main.
- **OBI-Calibration:** Tested on 826,638 records across 10 heterogeneous titles (AK-47 variants + stickers/pins/agents/capsules). Result: R² ≈ 0 for OBI→return regression on all tested titles — statistically null, NOT a data-volume problem. Conclusion: OBI works as a risk-gate filter (existing v17.3 architecture), not as a standalone trading signal. Branch feature/garch-ou-calibration NOT merged, kept as documented negative result.

## Active Branches
- `main` (infra-perimeter only).
- Active development isolated to `src/core/target_sniping/`.

## Guardrails & Enforcement Status
- **Git Push Protection:** Guardrail is active. However, its enforcement status is **SOFT** (OS-level wrapper), not HARD (no SELinux/container enforcement). Bypassing is possible but strictly forbidden without explicit reasoning logged.
- **Destructive Commands / Virtual Inventory:** Soft enforcement, relies on AI explicit confirmation and checking rules.

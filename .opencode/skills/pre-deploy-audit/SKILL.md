---
name: pre-deploy-audit
description: Use ONLY when the user asks to deploy, run in production, go live, or check production readiness. Trigger keywords: "deploy", "deploy checklist", "production", "продакшен", "go live", "live mode", "проверка перед запуском", "ready for production". Audits security, configuration, and code quality before enabling DRY_RUN=false.
---

# Pre-Deploy Audit

Run a comprehensive production-readiness check before going live with real money.

## Audit Checklist

### 1. Security

```bash
source .venv/bin/activate
python -c "
import os
checks = []

# ENCRYPTION_KEY must be set
key = os.getenv('ENCRYPTION_KEY')
checks.append(('ENCRYPTION_KEY set', bool(key and key != 'test-key' and key != 'validate-key')))

# API keys must not be test placeholders
pub = os.getenv('DMARKET_PUBLIC_KEY', '')
checks.append(('DMARKET_PUBLIC_KEY valid', len(pub) > 20 and 'test' not in pub.lower()))

sec = os.getenv('DMARKET_SECRET_KEY', '')
checks.append(('DMARKET_SECRET_KEY valid', len(sec) > 20 and '0'*64 not in sec))

# No debug flags
checks.append(('LOG_LEVEL is WARNING', os.getenv('LOG_LEVEL','INFO') in ('WARNING','ERROR')))

for name, ok in checks:
    print(f'  {\"✅\" if ok else \"❌\"} {name}')
print(f'\\nSecurity: {sum(1 for _,o in checks if o)}/{len(checks)}')
"
```

### 2. Configuration

```bash
source .venv/bin/activate
python -c "
from src.config import Config

print('  Strategy:', Config.ACTIVE_STRATEGY)
print('  DRY_RUN:', Config.DRY_RUN)
print('  TRADE_LOCK_HOURS:', Config.TRADE_LOCK_HOURS)
print('  FEE_RATE:', f'{Config.FEE_RATE*100:.1f}%')
print('  MIN_SPREAD_PCT:', f'{Config.MIN_SPREAD_PCT}%')
print('  MAX_SNIPING_PRICE_USD:', f'\${Config.MAX_SNIPING_PRICE_USD:.2f}')
print('  MAX_TOTAL_INVENTORY_VALUE:', f'\${Config.MAX_TOTAL_INVENTORY_VALUE:.2f}')
print('  MAX_TOTAL_INVENTORY_ITEMS:', Config.MAX_TOTAL_INVENTORY_ITEMS)
print('  CS2CAP_TIER:', Config.CS2CAP_TIER)
print('  MARKETPLACE_INSTANT_RESALE:', Config.MARKETPLACE_INSTANT_RESALE)
"
```

### 3. Balance

```bash
source .venv/bin/activate
python -c "
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config
import asyncio

async def check():
    api = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    balance = await api.get_real_balance()
    print(f'  DMarket Balance: \${balance:.2f}')
    min_needed = Config.MAX_SNIPING_PRICE_USD * 3
    print(f'  Minimum recommended: \${min_needed:.2f}')
    print(f'  Sufficient: {\"✅\" if balance >= min_needed else \"❌ (need more)\"}')
    await api.close()

asyncio.run(check())
"
```

### 4. Run Sandbox

```bash
source .venv/bin/activate
ENCRYPTION_KEY=\"\$ENCRYPTION_KEY\" python -m tests.sandbox_full_cycle
```

### 5. Code Quality

```bash
source .venv/bin/activate
ruff check src/ --select=F,E  # Only fatal/error checks
```

## Go/No-Go Criteria

| Check | Threshold |
|-------|-----------|
| Security | 3/3 must pass |
| DRY_RUN | Must be `false` |
| Balance | ≥ 3 × MAX_SNIPING_PRICE_USD |
| Sandbox | ≥ 1 profitable candidate |
| Ruff | 0 fatal errors |

## Related Files

- `.env` — All configuration
- `src/config.py` — Configuration class
- `src/utils/vault.py` — Secret management

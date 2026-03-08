# Project Structure (Updated 2026)

```
DMarket-Telegram-Bot/
├── .github/
│   ├── skills/              # Agent Skills (2026 Standard)
│   └── workflows/           # CI/CD (GitHub Actions)
├── src/
│   ├── dmarket/
│   │   ├── api/             # Modular Mixin-based API Client
│   │   ├── scanner/         # Arbitrage Scanning Engine
│   │   └── targets/         # Buy Order Management
│   ├── telegram_bot/
│   │   ├── handlers/
│   │   │   └── keyboard_parts/ # UI Components
│   │   └── notifications/
│   ├── ml/
│   │   └── parts/           # ML Components (Features, Pipeline)
│   ├── models/              # SQLAlchemy Models
│   └── utils/               # Shared Utilities
├── tests/                   # 150+ Stable Tests
├── docs/                    # Clean & Updated Documentation
├── data/                    # SQLite DB & Config Files
└── scripts/                 # Management Scripts
```

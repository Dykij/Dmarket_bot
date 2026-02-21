# System Flow Diagram: Critical Chain

This document visualizes the critical data flow for the DMarket Trading Bot, from user interaction/scheduler trigger to the final API call execution.

## Critical Chain Sequence

```mermaid
sequenceDiagram
    participant User as User/Scheduler
    participant TG as Telegram Bot
    participant TM as TradeManager (ArbitrageTrader)
    participant API as DMarketAPI (Client)
    participant Sign as Signer (Ed25519)
    participant Cache as Redis/Cache
    participant DM as DMarket Network

    User->>TG: Send Command / Trigger Scan
    TG->>TM: Initiate Trading Action (e.g., start_auto_trading)
    
    rect rgb(200, 255, 200)
        Note over TM, API: Core Trading Logic
        TM->>TM: check_limits()
        TM->>API: check_balance()
        API->>Cache: Check Cache (GET /balance)
        alt Cache Hit
            Cache-->>API: Return Cached Data
        else Cache Miss
            API->>Sign: generate_signature(method, path, body)
            Sign-->>API: Signed Headers (X-Request-Sign)
            API->>DM: HTTP GET /account/v1/balance
            DM-->>API: JSON Response
            API->>Cache: Store Result
        end
        API-->>TM: Balance Data
    end

    TM->>API: get_market_items(game, price_range)
    API->>DM: HTTP GET /exchange/v1/market/items
    DM-->>API: Market Listings
    
    loop Analysis
        TM->>TM: Calculate Profit (Buy + Fees < Sell)
        alt Profitable
            TM->>API: purchase_item(itemId, price)
            API->>Sign: Sign Transaction (POST)
            API->>DM: HTTP POST /exchange/v1/offers/create
            DM-->>API: Purchase Success
            
            TM->>API: list_item_for_sale(itemId, price)
            API->>Sign: Sign Listing (POST)
            API->>DM: HTTP POST /exchange/v1/user/items/sell
            DM-->>API: Listing Success
        end
    end

    TM-->>TG: Notify User (Success/Fail)
```

## Key Components

1.  **Telegram Handler (`src/telegram_bot`)**: Entry point for manual commands.
2.  **Trade Manager (`src/dmarket/arbitrage/trader.py`)**: Central logic for profit calculation, limits, and orchestration.
3.  **API Client (`src/dmarket/api/client.py`)**: Handles HTTP communication, rate limiting, and caching.
4.  **Signer (`nacl.signing`)**: Crucial security component. Requests *must* be signed with Ed25519 key.

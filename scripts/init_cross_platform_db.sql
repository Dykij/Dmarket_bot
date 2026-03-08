-- SQL Script to initialize cross-platform trading tracking
-- For use with SQLite / SQLAlchemy

CREATE TABLE IF NOT EXISTS cross_platform_trades (
    id VARCHAR(36) PRIMARY KEY, -- UUID
    item_id VARCHAR(255) NOT NULL, -- AssetID from DMarket
    game VARCHAR(50) NOT NULL,
    item_name TEXT NOT NULL,
    
    -- Buy Platform (Entry)
    buy_platform VARCHAR(50) DEFAULT 'dmarket',
    buy_price NUMERIC(18, 4) NOT NULL,
    buy_fee_percent NUMERIC(5, 2) DEFAULT 0.00, -- Top-up fee if applicable
    buy_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Status Tracking
    -- Statuses: 'at_dmarket', 'on_transfer', 'listed_externally', 'sold', 'failed', 'cancelled'
    status VARCHAR(50) NOT NULL DEFAULT 'at_dmarket',
    transfer_time TIMESTAMP, -- When sent to external market
    
    -- Sell Platform (Exit)
    sell_platform VARCHAR(50) DEFAULT 'waxpeer',
    target_sell_price NUMERIC(18, 4),
    sold_price NUMERIC(18, 4),
    sold_time TIMESTAMP,
    
    -- Performance Metrics
    net_profit NUMERIC(18, 4),
    roi_percent NUMERIC(10, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_cross_trades_status ON cross_platform_trades(status);
CREATE INDEX IF NOT EXISTS idx_cross_trades_asset ON cross_platform_trades(item_id);
CREATE INDEX IF NOT EXISTS idx_cross_trades_game ON cross_platform_trades(game);

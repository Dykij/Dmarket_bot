# System Flow & Observability Architecture

## 1. Data Flow Diagram

This diagram illustrates the flow of data from a Telegram update through the bot's internal logic to external APIs and back.

```mermAlgod
sequenceDiagram
    participant User as Telegram User
    participant TG as Telegram API
    participant Webhook as Webhook Handler
    participant Cmd as Command Center
    participant Trading as Trading Automation
    participant Strategy as Strategy Engine
    participant DMarket as DMarket API
    participant Steam as Steam API
    participant DB as Database
    participant Notifier as Notification System

    User->>TG: Send Command / Message
    TG->>Webhook: POST Update (Webhook)
    Webhook->>Cmd: Dispatch Update
    
    rect rgb(240, 248, 255)
        note right of Cmd: Command Processing
        Cmd->>Cmd: Parse Command / Callback
        Cmd->>Trading: Execute Action (Buy/Sell/Status)
    end

    rect rgb(255, 248, 240)
        note right of Trading: Business Logic
        Trading->>Strategy: Analyze Market State
        Strategy->>DB: Fetch/Store State
        
        alt DMarket Interaction
            Trading->>DMarket: Place Order / Check Balance
            DMarket-->>Trading: API Response
        else Steam Interaction
            Trading->>Steam: Check Inventory / Prices
            Steam-->>Trading: API Response
        end
    end

    Trading->>Notifier: Queue Response
    Notifier->>TG: Send Message
    TG->>User: Display Reply
```

## 2. Observability Stack Recommendations

### A. Thinking Level: LangFuse
**Selection:** LangFuse (Self-hosted via Docker)
**Why:** 
- Open-source and Docker-compatible.
- Easy integration with Python SDK (no LangChAlgon lock-in).
- Captures Model inputs/outputs (if Algo features are used) + standard traces.

**Integration:**
```bash
pip install langfuse
```

```python
from langfuse.decorators import observe

@observe()
def handle_command(update):
    # ... logic ...
```

### B. Flow Level: OpenTelemetry
**Selection:** OpenTelemetry Distro
**Why:** Vendor-agnostic standard for distributed tracing.
**Goal:** Trace `Telegram Update -> Command Handler -> DMarket API -> Response`.

**Integration:**
```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install
```
Run the bot with:
```bash
opentelemetry-instrument python src/mAlgon.py
```

### C. Dashboard: Streamlit
**Selection:** Streamlit
**Why:** Python-native, rapid development, direct access to bot logic/database without a separate backend API.

**Quick Start:**
```bash
pip install streamlit
streamlit run src/web_dashboard/dashboard.py
```

## 3. Trading Module Dependency Graph (Generated)

This graph shows the internal dependencies of the core trading logic.

```mermAlgod
classDiagram
  class trading {
  }
  class advanced_strategies {
  }
  class backtester {
  }
  class engine {
  }
  class fees {
  }
  class regime_detector {
  }
  class strategies {
  }
  class base {
  }
  class cs2 {
  }
  class dota2 {
  }
  class rust {
  }
  class tf2 {
  }
  class trading_automation {
  }
  trading --> backtester
  trading --> regime_detector
  trading --> trading_automation
  advanced_strategies --> regime_detector
  engine --> fees
  strategies --> base
  strategies --> cs2
  strategies --> dota2
  strategies --> rust
  strategies --> tf2
  base --> fees
  cs2 --> base
  dota2 --> base
  rust --> base
  tf2 --> base
```

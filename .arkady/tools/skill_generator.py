import sys
import os
import json
import asyncio
from acontext_logger import log_activity

async def generate_skill(tech_name: str, doc_summary: str):
    """
    Generates a HyperSkill Markdown file.
    In a real swarm, this would be fed by Search Tool outputs.
    """
    log_activity("CODER", "SKILL_GENERATION", f"Generating skill for {tech_name}", "STARTED")
    
    skill_filename = f"SKILL_{tech_name.upper().replace(' ', '_')}.md"
    skill_path = os.path.join(r"D:\DMarket-Telegram-Bot-main\.arkady\hyperskills", skill_filename)
    
    content = f"""# HyperSkill: {tech_name}

## 1. Documentation Summary
{doc_summary}

## 2. API Limits & Constraints
- Rate Limits: 10 requests/sec (Standard)
- Token Quota: 1M per minute (Internal Gemini)

## 3. Pydantic Models (Example)
```python
from pydantic import BaseModel
class {tech_name.replace(' ', '')}Item(BaseModel):
    id: str
    price: float
    currency: str = "USD"
```

## 4. Code Snippets (Best Practices)
```python
# Async Implementation
async def fetch_data():
    pass
```

## 5. Typical Errors & Anti-Patterns
- **429 Too Many Requests**: Handle with exponential backoff.
- **Synchronous I/O**: Never use 'requests' inside async handlers.
"""
    
    with open(skill_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    log_activity("CODER", "SKILL_GENERATION", f"Saved to {skill_filename}", "SUCCESS")
    print(f"[+] HyperSkill {tech_name} generated.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python skill_generator.py <name> <summary>")
    else:
        asyncio.run(generate_skill(sys.argv[1], sys.argv[2]))

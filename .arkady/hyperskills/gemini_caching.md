# HyperSkill: Gemini Context Caching
## Overview
Gemini 3 (Flash/Pro) supports context caching to reduce input token costs and avoid 429 Rate Limit errors when using large system prompts or long histories.

## Best Practices
- Cache content that remains static for multiple requests (System Prompt, Tools definition).
- Use `ttl` to manage cache lifetime (minimum 1 hour).
- Monitor `usage_metadata` to verify cache hits.

## Anti-Patterns
- Caching highly dynamic content (user messages that change every turn).
- Ignoring 429 errors without backoff.

## Implementation Example
```python
import google.generativeai as genai
from datetime import timedelta

def get_or_create_cache(name, content):
    # Check existing caches
    for c in genai.list_cached_contents():
        if c.display_name == name:
            return c
    
    # Create new cache if not found
    return genai.Caching.create(
        model='models/gemini-1.5-flash-001',
        display_name=name,
        contents=[content],
        ttl=timedelta(hours=1)
    )

# Wrapper logic for model call
def call_with_cache(model_name, prompt, cache_name):
    cache = get_or_create_cache(cache_name, "SYSTEM_PROMPT_HERE")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt, request_options={"cached_content": cache.name})
    return response
```

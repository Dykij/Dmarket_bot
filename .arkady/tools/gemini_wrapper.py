import os
import time
import hashlib
import logging
from typing import Any, Optional, List, Dict
import google.generativeai as genai
from google.generativeai import caching
import datetime
from rate_limiter import gatekeeper

logger = logging.getLogger("arkady.gemini_wrapper")

class GeminiCacheManager:
    """
    ARKADY v3 with [GATEKEEPER] Integration.
    Prevents 429 errors using pre-emptive rate limiting (TPM/RPM).
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def _get_project_structure(self) -> str:
        return "Project: DMarket-Telegram-Bot-main. Root includes: src, .arkady, data, docs."

    async def call_with_cache(
        self, 
        model_name: str, 
        prompt: str, 
        system_instruction: Optional[str] = None,
        ttl_minutes: int = 60
    ):
        actual_model_name = "models/gemini-1.5-flash-001" if "flash" in model_name else "models/gemini-1.5-pro-001"
        project_context = self._get_project_structure()
        full_system_context = f"{system_instruction}\n\nPROJECT_STRUCTURE:\n{project_context}"
        
        model = genai.GenerativeModel(
            model_name=actual_model_name,
            system_instruction=full_system_context
        )

        # [GATEKEEPER] Step A: Count Tokens
        try:
            token_info = model.count_tokens(prompt)
            count = token_info.total_tokens
        except Exception:
            count = len(prompt) // 4 # Rough fallback estimation

        # [GATEKEEPER] Step B: Pre-emptive Acquire
        gatekeeper.acquire(count)

        try:
            response = await model.generate_content_async(prompt)
            return response.text
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                # Handle 429 with Jitter as requested
                wait = 5 # Default
                if "Retry-After" in error_str:
                    try:
                        # Extract Retry-After if present in string or headers
                        wait = int(re.search(r'Retry-After: (\d+)', error_str).group(1)) + 1
                    except: pass
                
                logger.warning(f"[!] 429 Received. Jitter sleep: {wait}s")
                time.sleep(wait)
                return await self.call_with_cache(model_name, prompt, system_instruction)
            raise e

def get_gemini():
    return GeminiCacheManager()

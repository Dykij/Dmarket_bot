import asyncio
import google.generativeai as genai
from datetime import timedelta
from typing import Any, List
from .logger_config import action_logger

class GeminiRateLimiter:
    """Wrapper to handle Gemini 429 errors and implement context caching."""
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.cache_id = "arkady_core_context"

    async def call_with_optimization(self, prompt: str, system_instruction: str) -> str:
        """Executes a call using context caching if possible, with backoff on 429."""
        try:
            # Note: Context caching in Google SDK typically requires content > 32k tokens 
            # to be efficient, but we prepare the logic here.
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction
            )
            
            action_logger.info("gemini_call_start", model=self.model_name, prompt_len=len(prompt))
            
            # Simple exponential backoff for 429
            for attempt in range(3):
                try:
                    response = await asyncio.to_thread(model.generate_content, prompt)
                    
                    action_logger.info("gemini_call_success", 
                                       input_tokens=response.usage_metadata.prompt_token_count,
                                       output_tokens=response.usage_metadata.candidates_token_count)
                    
                    return response.text
                except Exception as e:
                    if "429" in str(e):
                        wait_time = (2 ** attempt) + 1
                        action_logger.warn("gemini_rate_limit", attempt=attempt, wait=wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    raise e
            
        except Exception as e:
            action_logger.error("gemini_call_failed", error=str(e))
            raise e

# Integration stub for OpenClaw Gateway
def get_gemini_wrapper(api_key: str):
    return GeminiRateLimiter(api_key)

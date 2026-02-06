import asyncio
import os
import sys

# Добавляем путь к конфигурации
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))

from gemini_wrapper import GeminiCacheManager

async def test_wrapper():
    print("[*] Testing GeminiCacheManager...")
    
    # Инициализация менеджера (API ключ подтянется из env)
    try:
        manager = GeminiCacheManager()
        
        # Тестовый вызов
        model = "gemini-1.5-flash" # Используем стабильное имя
        instruction = "You are Arkady's internal test module. Reply with 'ACK' if you receive this."
        prompt = "System check: wrapper connectivity test."
        
        print(f"[*] Dispatching test call to {model}...")
        response = await manager.call_with_cache(
            model_name=model,
            prompt=prompt,
            system_instruction=instruction
        )
        
        print(f"[+] Response received: {response}")
        
        if "ACK" in response.upper():
            print("[SUCCESS] Gemini Wrapper is functional and cache-ready.")
        else:
            print("[WARNING] Response received but 'ACK' not found. Check logic.")
            
    except Exception as e:
        print(f"[ERROR] Wrapper test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_wrapper())


import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

class AIModel:
    def __init__(self, api_key=None, model_name="gemini-1.5-flash"):
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found. Please set it in environment variables.")
        
        genai.configure(api_key=self.api_key)
        
        # Generation config for lightweight, fast responses
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 512,
            "response_mime_type": "text/plain",
        }
        
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        self.chat_session = self.model.start_chat(history=[])

    def generate_response(self, prompt: str) -> str:
        try:
            response = self.chat_session.send_message(prompt)
            return response.text
        except Exception as e:
            return f"Error generating response: {str(e)}"

def load_ai(api_key=None):
    print("Loading lightweight Gemini 1.5 Flash client...")
    return AIModel(api_key=api_key)

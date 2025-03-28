import os
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio
import json
from constants.Gemini_system_prompt import GEMINI_PROMPT
from constants.Semantic_cache_prompt import Semantic_cache_prompt
from utils.Query_Processor import QueryProcessor
import re
import time
import google.api_core.exceptions
import traceback
from google.genai.types import Content

load_dotenv()
qp = QueryProcessor()

async def response_strategy(message: str, chat, is_deep_search=False):
    try:
        async def chat_with_bot(user_input):
            response = chat.send_message(user_input)
            return response.text

        async def interactive_chat(user_input=message):
            if not user_input.strip():
                return {"response": "Empty input", "references": [], "code": 200}
            
            retries = 3  # Number of retries for quota errors
            base_delay = 2  # Initial delay in seconds
            for attempt in range(retries):
                try:
                    bot_reply = await chat_with_bot(user_input)
                    break
                except google.api_core.exceptions.ResourceExhausted:
                    if attempt == retries - 1:
                        return {"response": "Service unavailable due to quota limits. Please try again later.", "references": [], "code": 429}
                    wait_time = base_delay * (2 ** attempt)
                    print(f"Quota exceeded, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            
            json_data = json.loads(bot_reply)

            print(json_data)
            answer = {}  # Initialize answer dictionary here
            
            if json_data.get("retrieve"):
                answer = await qp.process_query(json_data["query"], json_data["knowledge"], is_deep_search)
                answer["retrieve"] = True
                chat.record_history(
                    user_input = "",
                    model_output=[Content(parts=[{"text": json.dumps(answer, indent=2)}], role="model")],
                    is_valid=True,
                    automatic_function_calling_history=None
                )
            else:
                answer["retrieve"] = False
                answer["answer"] = json_data.get("answer", "No answer found.")
                answer["links"] = json_data.get("links", [])
            
            return {"response": answer["answer"], "references": answer["links"], "code": 200}

        return await interactive_chat(message)
    except google.api_core.exceptions.ResourceExhausted:
        return {
            "response": "Quota limit exceeded. Please wait before trying again.",
            "references": [],
            "code": 429
        }
    except Exception as e:
        detailed_error = traceback.format_exc()
        print("Detailed error:", detailed_error)
        return {
            "response": f"Error generating response, please try again later.",
            "references": [],
            "code": 400
        }

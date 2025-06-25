import os, traceback, copy, aiohttp
from .llm_base import LLMBase
from .prompts import SYSTEM_PROMPT_MOOD_MATCHING
import logging, json
from typing import List, Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class MoodMatching:
    
    def __init__(
            self,
            provider_models: Dict
        ):
        self.provider_models = copy.deepcopy(provider_models)
        provider_name=os.getenv("PROVIDER_NAME")
        provider_name = "openai" if not isinstance(provider_name, str) or self.provider_models.get(provider_name) is None else provider_name
        openai_setting = self.provider_models.get(provider_name).get("openai_setting")
        openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
        self.generation_params = self.provider_models.get(provider_name).get("generation_params")
        self.llm = LLMBase(
            openai_setting=openai_setting,
            provider_name=provider_name,
        )

    async def callAPIGetMood(self, bot_id: int = None):
        try:
            async with aiohttp.ClientSession() as session:
                url = os.getenv("URL_MOOD_DESCRIPTION")
                params = {"token": os.getenv("TOKEN_MOOD_DESCRIPTION")}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("data", [])
                    else:
                        logging.error(f"Failed to get moods. Status: {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Error getting moods: {str(e)}")
            return None

    async def process(
            self, 
            bot_id: int = None,
            conversation_history: List[Dict] = [],
            **kwargs
        ):
        try:
            # max_term_concern = 3 
            mood_list = await self.callAPIGetMood(bot_id)
            if not mood_list:
                return None
            system_prompt = SYSTEM_PROMPT_MOOD_MATCHING.replace("{{MOOD_LIST_DESCRIPTION}}", json.dumps(mood_list, ensure_ascii=False, indent=4))
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]
            content = []
            if conversation_history and isinstance(conversation_history, list):
                for messsage in conversation_history:
                    if messsage.get("role") in ["user", "assistant"]:
                        content.append(messsage.get("role") + ": " + messsage.get("content"))
            if not content:
                return None
            content = "\n ".join(content)
            messages.append(
                {
                    "role": "user",
                    "content": content
                }
            )

            response = await self.llm.get_response(
                messages,
                **self.generation_params
            )

            print(f"[MOOD_MATCHING][INFO] Response: {response}")
            return response
        except Exception as e:
            logging.error(traceback.format_exc())
            return None


import os, copy, random, json
import logging
import aiohttp
import traceback
from .prompt import format_text_from_input_slots, get_value_of_slot_from_input
from typing import List
from src.utils.utils import call_api_get_profile_description
from src.chatbot.llm_base import BaseLLM
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class PromptProcessor:
    def __init__(self):
        pass

    def regex_slot_in_text(self, text: str, pattern = r"\{\{([^\{\}]+)\}\}"):
        if not isinstance(text, str):
            return []
        matches = re.findall(pattern, text)
        return [match for match in matches]
    
    async def find_profile_into_scenario(self, prompt: str) -> dict:
        slots = self.regex_slot_in_text(
            text = prompt,
            pattern=r"\[\[[^\]]+\]\]",
        )
        if not isinstance(slots, list):
            return {}
        profile_params = []
        for slot in slots:
            if slot not in profile_params:
                profile_params.append(slot)
        profile_description = await call_api_get_profile_description()
        profile_slots = {}
        for description in profile_params:
            variable_name = await self.api_profile_matching(
                conversation_id="INIT",
                message=description,
                profile_description=profile_description,
            )
            profile_slots[description] = variable_name
        return profile_slots
    
    async def api_profile_matching(self, conversation_id: str, message: str, profile_description: dict):
        try :
            if not isinstance(profile_description, dict) or len(profile_description) == 0:
                return None
            headers = {'Content-Type': 'application/json'}
            url = os.getenv("TOOL_EXECUTOR_URL") + "/profileMatching"
            payload = {
                "conversation_id": conversation_id,
                "message": message,
                "profile_description": profile_description,
            }
            logging.info(f"[api_profile_matching]================: {url}/profileMatching - {payload}")
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if isinstance(result, dict):
                            if result.get('status') == 0 and result.get("result") is not None:
                                return result.get("result")
            return None
        except Exception as e:
            logging.info(f"[ERROR] async_webhook: {traceback.format_exc()}")
            return None
        
    def update_data_from_profile(self, prompt:str, slots: dict):
        try :
            # text = json.dumps(data, ensure_ascii=False, indent=4)
            if isinstance(slots, dict) and len(slots) > 0:
                for key, value in slots.items():
                    if value is not None:
                        prompt = prompt.replace(key, "{{" + str(value) + "}}")
            return prompt
        except:
            logging.info(f"[ERROR] update_data_from_profile: {traceback.format_exc()}")
            return prompt
        
    async def process_profile_slots(self, prompt: str):
        profile_slots = await self.find_profile_into_scenario(prompt)
        logging.info(f"[process_profile_slots]================: {profile_slots}")
        post_prompt = self.update_data_from_profile(prompt, profile_slots)
        return post_prompt
        
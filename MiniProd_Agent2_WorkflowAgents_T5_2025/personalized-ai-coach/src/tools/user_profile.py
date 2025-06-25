from typing import List
import os, copy, re, logging, traceback, json, aiohttp, requests
import asyncio
from src.utils.utils import call_api_get_profile_description
from src.chatbot.prompt import format_prompt_from_variable, SYSTEM_PROMPT_EXTRACTION_PROFILE, get_system_conversation_history


URL_PROFILE = os.getenv("URL_PROFILE")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class UserProfile:
    
    def format_text_from_input_slots(self, input_slots: dict, text: str):
        if not isinstance(input_slots, dict) or not isinstance(text, str):
            return text
        text = re.sub(r'\s+', ' ', text)
        slots = self.regex_slot_in_text(
            text=text
        )
        for slot in slots:
            value = self.get_value_of_slot_from_input(
                slot=slot,
                input_slots=input_slots,
            )
            if value is not None:
                text = text.replace("{{" + slot + "}}", str(value))
        return text
    
    def preprocess_scenario(self, scenario: dict, input_slots: dict):
        try :
            scenario_normal = copy.deepcopy(scenario)
            for idx, element in enumerate(scenario_normal):
                title = self.format_text_from_input_slots(
                    input_slots=input_slots,
                    text=element.get('TITLE')
                )
                scenario_normal[idx]["TITLE"] = title
                # for intent_name, value in element.get("FLOWS").items():
                #     for idx_flow, item in enumerate(value):
                #         for idx_response, text in enumerate(item.get("RESPONSE")):
                #             scenario_normal[idx]["FLOWS"][intent_name][idx_flow]["RESPONSE"][idx_response] = self.format_text_from_input_slots(
                #                 input_slots=input_slots,
                #                 text=text
                #             )
            return scenario_normal
        except :
            logging.info(f"[ERROR] preprocess_scenario: {traceback.format_exc()}")
            return scenario

    def regex_slot_in_text(self, text: str, pattern = r"\{\{([^\{\}]+)\}\}"):
        if not isinstance(text, str):
            return []
        matches = re.findall(pattern, text)
        return [match for match in matches]
    
    def get_value_of_slot_from_input(self, slot: str, input_slots: dict):
        sub_slots = slot.split("/")
        values = copy.deepcopy(input_slots)
        for sub in sub_slots:
            if isinstance(values, dict) and values.get(sub) is not None:
                values = values.get(sub)
            else :
                if isinstance(values, list) and sub.isdigit() == True:
                    values = values[int(sub)]
                else :
                    return None
        return values
    
    async def find_profile_into_scenario(self, data: List[dict]) -> dict:
        text = json.dumps(data, ensure_ascii=False, indent=4)
        slots = self.regex_slot_in_text(
            text = text,
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
    
    def fill_slot_profile(self, text: str, slots: dict):
        if isinstance(slots, dict) and len(slots) > 0 and isinstance(text, str):
            for key, value in slots.items():
                if value is not None:
                    text = text.replace(key, "{{" + str(value) + "}}")
        return text
    
    def update_data_from_profile(self, data: List[dict], slots: dict):
        try :
            text = json.dumps(data, ensure_ascii=False, indent=4)
            if isinstance(slots, dict) and len(slots) > 0:
                for key, value in slots.items():
                    if value is not None:
                        text = text.replace(key, "{{" + str(value) + "}}")
            text = json.loads(text)
            return text
        except:
            logging.info(f"[ERROR] update_data_from_profile: {traceback.format_exc()}")
            return data
        

    def get_message_of_profile(self, 
        input_slots: dict,
        system_extraction_profile: str,
        history: str,
        **kwargs
    ) -> dict :
        # async def run_param_extractor(self, task_chain, history, task_idx, llm_base, generation_params, system_context_variables):
        ## EXTRACTIION CONTEXT
        if isinstance(system_extraction_profile, str):
            system_extraction_profile = system_extraction_profile.replace("{{", "")
            system_extraction_profile = system_extraction_profile.replace("}}", "")
        
        if history is None or not isinstance(history, list):
            return None
        
        conversation_history = get_system_conversation_history(history)
        variables = {}
        variables["SYSTEM_EXTRACTION_PROFILE"] = system_extraction_profile
        if system_extraction_profile:
            messages = [
                {
                    "role": "system",
                    "content": copy.deepcopy(SYSTEM_PROMPT_EXTRACTION_PROFILE),
                },
                {
                    "role": "user",
                    "content": conversation_history
                }
            ]
            messages = format_prompt_from_variable(prompt=messages, variables=variables)
            return messages
        return None


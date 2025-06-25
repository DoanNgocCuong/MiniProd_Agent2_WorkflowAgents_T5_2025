import os, copy, random, json
import logging
import aiohttp
import traceback
from .prompt import format_text_from_input_slots, get_value_of_slot_from_input
from typing import List
import re
from src.utils.utils import call_api_get_user_profile
from src.chatbot.material_gen import PromptProcessor
from src.chatbot.llm_base import BaseLLM
from src.chatbot.condition import Condition


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class LessonPolicies:

    def __init__(self, config: dict):
        self.error_message = {
            "status": "END",
            "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
            "conversation_id": None,
        }
        self.prompt_processor = PromptProcessor()
        self.config = config
        self.llm_client = BaseLLM(
            openai_setting=self.config.get("PROVIDER_MODELS").get("openai").get("openai_setting"),
            provider_name="openai",
        )
        self.llm_params = self.config.get("PROVIDER_MODELS").get("openai").get("generation_params")
        self.condition = Condition()


    def get_message_error(self, conversation_id: str, message_error: str) -> str:
        return {
            "status": "END",
            "text": [
                {
                    "text": "Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"
                }
            ],
            "conversation_id": conversation_id,
            "msg": f"Bad request {message_error}",
            "mood": "",
            "image": "",
            "video": "",
            "robot_type": None,
        }

    async def process(self, 
        scenario: dict, 
        message: str, 
        record: dict,
        input_slots: dict,
        config: dict, 
        conversation_id: str,
        audio_url: str = "",
        **kwargs) -> str:
        
        record_new = copy.deepcopy(record)
        cur_task_status = record_new.get("CUR_TASK_STATUS")
        next_action = record_new.get("NEXT_ACTION")
        logging.info(f"===================next_action: {next_action} - cur_task_status: {cur_task_status}")
        previous_next_action = copy.deepcopy(next_action)
        first_message = None
        slots_new = None

        if message == "[NEXT]":
            if next_action < len(scenario) - 1:
                next_action += 1
                record_new["CUR_TASK_STATUS"] = "END"
                record_new["NEXT_ACTION"] = next_action - 1 
                record_new["PREVIOUS_NEXT_ACTION"] = previous_next_action
                return "ACTION", {"status": "END", "text": [""]}, record_new, slots_new

        if cur_task_status in ["INIT", "END"]:
            first_message = message if message else "alo"
            next_action += 1

            if cur_task_status == "END":
                previous_next_action_record = record_new.get("PREVIOUS_NEXT_ACTION")
                if previous_next_action_record is not None:
                    previous_next_action_record = next_action - 1
                response_extractor = await self.callAPIRunExtractAndGeneration(
                    config=config,
                    task=scenario[previous_next_action_record],
                    conversation_id=conversation_id,
                )
                # logging.info(f"=============response_extractor: {response_extractor}")
                slots_new = self.get_pram_extractor(
                    res=response_extractor,
                    pram=scenario[previous_next_action_record].get("param_extractor")
                )
                if isinstance(slots_new, dict) and len(slots_new) > 0:
                    input_slots.update(slots_new)

            ## Set Variable:
            gen_material = scenario[next_action].get("gen_material")
            logging.info(f"[Lesson Policies Generate Material]: {conversation_id} - gen_material {gen_material} - scenario {scenario[next_action]}")
            if gen_material:
                # profile_slots = await self.prompt_processor.find_profile_into_scenario(gen_material)
                # logging.info(f"[Lesson Policies]: {conversation_id} - profile_slots {profile_slots}")
                # material_prompt = self.prompt_processor.update_data_from_profile(gen_material, profile_slots)
                # user_profile = await call_api_get_user_profile(conversation_id=conversation_id)
                # is_contain_slots_values = True
                # if isinstance(profile_slots, dict):
                #     for key, value in profile_slots.items():
                #         if value and user_profile and user_profile.get(value) is None:
                #             is_contain_slots_values = False
                #             break
                user_profile = await call_api_get_user_profile(conversation_id=conversation_id)
                # logging.info(f"[Lesson Policies]: {conversation_id} - user_profile {material_prompt}")
                # if user_profile and is_contain_slots_values:    
                if user_profile:    
                    for key, value in user_profile.items():
                        if value is None:
                            value = "NULL"
                        gen_material = gen_material.replace("{{" + key + "}}", str(value))
                    material_response = await self.llm_client.get_response(
                        messages=[
                            {"role": "system", "content": gen_material}
                        ],
                        **self.llm_params
                    )
                    materials = self.llm_client.parsing_json(
                        data=material_response
                    )
                    logging.info(f"[Lesson Policies]: {conversation_id} - materials {materials}")
                    if isinstance(materials, dict):
                        for key, value in materials.items():
                            input_slots[key] = value

            slots_new = self.set_variables_into_input_slots(
                variables=scenario[next_action].get("set_variable"),
                input_slots=input_slots
            )
            if isinstance(slots_new, dict):
                input_slots.update(slots_new)

            ## Process Condition
            if scenario[next_action].get("robot_type") == "Condition":
                rule = self.condition.process(
                    condition=scenario[next_action].get("condition"),
                    input_slots=input_slots
                )
                if rule:
                    scenario[next_action]["robot_type"] = rule.get("robot_type")
                    scenario[next_action]["robot_type_id"] = rule.get("robot_type_id")
                    record_new["RULE"] = rule
            ## END Process Condition

            ## END Set Variable
            response_init = await self.callAPIInitConversation(
                task=scenario[next_action],
                config=config,
                conversation_id=conversation_id,
                input_slots=input_slots,
                user_id=kwargs.get("user_id")
            )
            logging.info(f"[Lesson Policies]: {conversation_id} - response_init {response_init} - scenario[next_action]: {scenario[next_action]}")
            if not isinstance(response_init, dict) or response_init.get("status") != 0:
                record_new["CUR_TASK_STATUS"] = "ERROR"
                record_new["NEXT_ACTION"] = next_action
                record_new["PREVIOUS_NEXT_ACTION"] = previous_next_action
                return "ERROR", response_init, record_new, slots_new
            else :
                response_webhook = await self.callAPIWebhook(
                    task=scenario[next_action],
                    config=config,
                    conversation_id=conversation_id,
                    first_message=first_message,
                    message=message,
                    audio_url=audio_url,
                )
                logging.info(f"[Lesson Policies]: {conversation_id} - response_webhook {response_webhook}")
                if not response_webhook or response_webhook.get("status") == "ERROR":
                    record_new["CUR_TASK_STATUS"] = "ERROR"
                    record_new["NEXT_ACTION"] = next_action
                    record_new["PREVIOUS_NEXT_ACTION"] = previous_next_action
                    return "ERROR", response_webhook, record_new, slots_new
                else :
                    record_new["CUR_TASK_STATUS"] = response_webhook.get("status")
                    record_new["NEXT_ACTION"] = next_action
                    record_new["PREVIOUS_NEXT_ACTION"] = previous_next_action
                    status = response_webhook.get("status")
                    if response_webhook.get("status") == "END":
                        if next_action < len(scenario) - 1:
                            status = "ACTION"
                        else :
                            status = "END"
                        slots_new = self.get_pram_extractor(
                            res=response_webhook,
                            pram=scenario[next_action].get("param_extractor")
                        )
                    return status, response_webhook, record_new, slots_new
        else :
            response_webhook = await self.callAPIWebhook(
                task=scenario[next_action],
                config=config,
                conversation_id=conversation_id,
                first_message=first_message,
                message=message,
                audio_url=audio_url,
            )
            logging.info(f"[Lesson Policies]: {conversation_id} - response_webhook {response_webhook}")
            if not response_webhook or response_webhook.get("status") == "ERROR":
                record_new["CUR_TASK_STATUS"] = "ERROR"
                record_new["NEXT_ACTION"] = next_action
                return "ERROR", response_webhook, record_new, slots_new
            else :
                record_new["CUR_TASK_STATUS"] = response_webhook.get("status")
                record_new["NEXT_ACTION"] = next_action
                status = response_webhook.get("status")
                if response_webhook.get("status") == "END":
                    if next_action < len(scenario) - 1:
                        status = "ACTION"
                    else :
                        status = "END"
                        
                    slots_new = self.get_pram_extractor(
                            res=response_webhook,
                        pram=scenario[next_action].get("param_extractor")
                    )
                return status, response_webhook, record_new, slots_new

    async def callAPIInitConversation(self, task: dict, config: dict, conversation_id: str, input_slots: dict, **kwargs):
        robot_type = task.get("robot_type")
        robot_type_id = task.get("robot_type_id")
        if not isinstance(config.get(robot_type), dict):
            return None
        url = config.get(robot_type).get("url") + "/initConversation"
        headers = config.get(robot_type).get("headers")
        method = config.get(robot_type).get("method")
        payload = config.get(robot_type).get("payload")
        if robot_type == "Agent":
            payload = {
                "conversation_id": conversation_id,
                "input_slots": input_slots,
                "bot_id": robot_type_id,
            }
        else :
            payload = {
                "conversation_id": conversation_id,
                "input_slots": input_slots,
                "bot_id": robot_type_id,
            }
        user_id = kwargs.get("user_id")
        if user_id:
            payload["user_id"] = user_id
        return await self.async_call_api(
            url = url,
            payload=payload,
            headers=headers,
            method=method,
            conversation_id=conversation_id,
        )
    
    async def callAPIWebhook(self, task: dict, config: dict, conversation_id: str, message: str, first_message: str = None, audio_url: str = None, **kwargs):
        robot_type = task.get("robot_type")
        if not isinstance(config.get(robot_type), dict):
            return None
        url = config.get(robot_type).get("url") + "/webhook"
        headers = config.get(robot_type).get("headers")
        method = config.get(robot_type).get("method")
        payload = {
            "conversation_id": conversation_id,
            "message": message,
            "audio_url": audio_url if audio_url is not None else "",
        }
        if first_message:
            payload["first_message"] = message
        return await self.async_call_api(
            url = url,
            payload=payload,
            headers=headers,
            method=method,
            conversation_id=conversation_id,
        )
    
    async def callAPIRunExtractAndGeneration(self, task: dict, config: dict, conversation_id: str, **kwargs):
        robot_type = task.get("robot_type")
        if not isinstance(config.get(robot_type), dict):
            return None
        url = config.get(robot_type).get("url") + "/runExtractAndGeneration"
        headers = config.get(robot_type).get("headers")
        method = config.get(robot_type).get("method")
        payload = {
            "conversation_id": conversation_id,
        }
        return await self.async_call_api(
            url = url,
            payload=payload,
            headers=headers,
            method=method,
            conversation_id=conversation_id,
        )
    
    async def async_call_api(self, url: str, headers: dict = {}, payload = {}, method = "POST", timeout: int = 15, **kwargs):
        try :
            if method == "GET":
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=timeout) as response:
                        logging.info(f"[async_call_api]: method: {method} - url : {url} - headers: {headers} - payload: {payload} - response: {await response.text()}")
                        if response.status == 200:
                            return await response.json()
                        else :
                            return {}
            else :
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=timeout) as response:
                        logging.info(f"[async_call_api]: method: {method} - url : {url} - headers: {headers} - payload: {payload} - response: {await response.text()}")
                        if response.status == 200:
                            return await response.json()
                        else :
                            return {}
        except :
            logging.info(f"[ERROR Call API] {kwargs.get('conversation_id')} - url : {url} - payload: {payload}: {traceback.format_exc()}")
            return {}
    
    def get_pram_extractor(self, pram: str, res: dict) -> dict:
        try :
            if not pram:
                return None
            pram = json.loads(pram)
            slots = {}
            for key in pram:
                value = None
                if isinstance(key, str):
                    if isinstance(res.get("record"), dict):
                        if res.get("record").get(key) is not None:
                            value = res.get("record").get(key)
                    if isinstance(res.get('SYSTEM_CONTEXT_VARIABLES'), dict):
                        if res.get("SYSTEM_CONTEXT_VARIABLES").get(key) is not None:
                            value = res.get("SYSTEM_CONTEXT_VARIABLES").get(key)
                    if value is not None:
                        slots[key] = copy.deepcopy(value)
            return slots
        except:
            logging.info(f"[ERROR] get_pram_extractor ===========: {pram} - {traceback.format_exc()}")
            return None
        
    def set_variables_into_input_slots(self, variables: dict, input_slots) -> dict:
        try :
            slots = {}
            variables = self.parsing_json(text=variables)
            if isinstance(variables, dict) and isinstance(input_slots, dict):
                for key, value in variables.items():
                    value_fill = get_value_of_slot_from_input(
                        slot = value,
                        input_slots = input_slots,
                    )
                    # logging.info(f"========================key: {key} - value: {value} - value_fill: {value_fill}")
                    slots[key] = value_fill
                return slots
            else :
                return variables if isinstance(variables, dict) else {}
        except:
            logging.info(f"[ERROR] get_pram_extractor ===========: {traceback.format_exc()}")
            return None
        

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
    
    def parsing_json(self, text: str) -> dict:
        try :
            if isinstance(text, dict):
                return text
            if isinstance(text, str):
                return json.loads(text)
        except:
            return text
    
    def update_task(self, scenario: List[dict], next_action: int, trigger: dict) -> dict:
        logging.info(f"================== scenario: {scenario} - next_action: {next_action} - trigger: {trigger}")
        if not isinstance(scenario, list) or not isinstance(next_action, int) or next_action >= len(scenario):
            return scenario, next_action
        for i in range(next_action+1, len(scenario), 1):
            if scenario[i].get("robot_type") == "Trigger":
                if isinstance(trigger, dict) and trigger.get("robot_type") and trigger.get("robot_type_id"):
                    scenario[i]["robot_type"] = trigger.get("robot_type")
                    scenario[i]["robot_type_id"] = trigger.get("robot_type_id")
                    return scenario, i - 1
                else :
                    continue
            else :
                return scenario, i-1
        return scenario, len(scenario)

    def update_task_condition(self, task: dict, input_slots: dict) -> dict:
        condition = task.get("condition")
        for item in condition:
            return None
        

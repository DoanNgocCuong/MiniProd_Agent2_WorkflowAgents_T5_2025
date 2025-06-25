from typing import List
import os, copy, re, logging, traceback, json, aiohttp, requests
import asyncio
from src.utils.utils import call_api_get_profile_description


INTENT_FALLBACK = os.getenv("INTENT_FALLBACK") if os.getenv("INTENT_FALLBACK") is not None else "fallback"
URL_PROFILE = os.getenv("URL_PROFILE")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class ScenarioExcel:

    def norm_start_message_dict(self, start_message: str, cur_action: dict = None) -> dict:
        start_message_parsing = self.parsing(start_message, typeofvalue="json")
        if isinstance(start_message_parsing, dict) or isinstance(start_message_parsing, list):
            start_message = start_message_parsing
        if isinstance(start_message, dict) or isinstance(start_message, list):
            return start_message
        return [
            {
                "text": start_message,
                "mood":"" if not isinstance(cur_action, dict) else cur_action.get("MOOD"),
                "image":"" if not isinstance(cur_action, dict) else cur_action.get("IMAGE"),
                "video":"" if not isinstance(cur_action, dict) else cur_action.get("VIDEO"),
                "moods":[] if not isinstance(cur_action, dict) else cur_action.get("MOODS"),
                "voice_speed":"" if not isinstance(cur_action, dict) else cur_action.get("VOICE_SPEED"),
                "text_viewer":"" if not isinstance(cur_action, dict) else cur_action.get("TEXT_VIEWER"),
                "volume": "" if not isinstance(cur_action, dict) else cur_action.get("VOLUME"),
                "audio": "" if not isinstance(cur_action, dict) else cur_action.get("AUDIO"),
                "model": "" if not isinstance(cur_action, dict) else cur_action.get("MODEL"),
            }
        ]

    def convert_data_excel_to_scenario(self, start_message: str, data: List[dict]) -> dict:
        """
            [
                {
                    "TITLE": int,
                    "FLOWS": {
                        "intent_name": [
                            {
                                "RESPONSE": [List[str]],
                                "TOOL": [ANY],
                                "NEXT_ACTION": int
                            }
                        ]
                    }
                }
            ]
        """
        scenario = []
        if start_message is not None:
            scenario.append({
                "TITLE": "",
                "FLOWS": {
                    INTENT_FALLBACK: [
                        {
                            "RESPONSE": [self.norm_start_message_dict(start_message)],
                            "TOOL": [],
                            "NEXT_ACTION": 1,
                            "INTENT_DESCRIPTION": "",
                            "REGEX_POSITIVE": [],
                            "REGEX_NEGATIVE": [],
                            "MOOD": self.get_mood(data=data[0]),
                            "IMAGE": self.get_image(data=data[0]),
                            "VIDEO": self.get_video(data=data[0]),
                            "MOODS": self.get_moods(data=data[0]),
                            "LISTENING_ANIMATIONS": self.get_listening_aninimations(data=data[0]),
                            "LANGUAGE": self.get_language(data=data[0]),
                            "VOICE_SPEED": self.get_voice_speed(data=data[0]),
                            "VOLUME": self.get_volume(data=data[0]),
                            "TEXT_VIEWER": self.get_text_viewer(data=data[0]),
                            "AUDIO_LISTENING": self.get_audio_listening(data=data[0]),
                            "IMAGE_LISTENING": self.get_image_listening(data=data[0]),
                        }
                    ]
                }
            })
        else :
            scenario.append({
                "TITLE": "",
                "FLOWS": {
                    INTENT_FALLBACK: [
                        {
                            "RESPONSE": [self.norm_start_message_dict(data[0].get("QUESTION"))],
                            "TOOL": [],
                            "NEXT_ACTION": 1,
                            "INTENT_DESCRIPTION": "",
                            "REGEX_POSITIVE": [],
                            "REGEX_NEGATIVE": [],
                            "MOOD": self.get_mood(data=data[0]),
                            "IMAGE": self.get_image(data=data[0]),
                            "VIDEO": self.get_video(data=data[0]),
                            "MOODS": self.get_moods(data=data[0]),
                            "LISTENING_ANIMATIONS": self.get_listening_aninimations(data=data[0]),
                            "LANGUAGE": self.get_language(data=data[0]),
                            "VOICE_SPEED": self.get_voice_speed(data=data[0]),
                            "VOLUME": self.get_volume(data=data[0]),
                            "TEXT_VIEWER": self.get_text_viewer(data=data[0]),
                            "AUDIO_LISTENING": self.get_audio_listening(data=data[0]),
                            "IMAGE_LISTENING": self.get_image_listening(data=data[0]),
                        }
                    ]
                }
            })
        if isinstance(data, list):
            flow = {}
            pre_data = None
            for idx, element in enumerate(data):
                status, value = self.set_questions(data=element)
                if status == True:
                    if len(flow) > 0 and isinstance(flow.get("FLOWS"), dict) and len(flow.get("FLOWS")) > 0:
                        scenario.append(copy.deepcopy(flow))
                    flow = value
                    pre_data = {}
                else :
                    if element.get("INTENT_NAME"):
                        pre_data = element
                    flow = self.set_flow_with_intent_name(
                        flow=flow,
                        data=element,
                        pre_data=pre_data
                    )
                    if idx + 1 >= len(data):
                        if len(flow) > 0 and isinstance(flow.get("FLOWS"), dict) and len(flow.get("FLOWS")) > 0:
                            scenario.append(copy.deepcopy(flow))
        scenario = self.set_next_actions(scenario=scenario)
        return scenario
    
    def set_next_actions(self, scenario: List[dict]) -> List[dict]:
        for idx, data in enumerate(scenario):
            for intent_name, value in data.get("FLOWS").items():
                for idx_flow, flow in enumerate(value):
                    if idx_flow >= len(value) - 1:
                        scenario[idx]["FLOWS"][intent_name][idx_flow]["NEXT_ACTION"] = idx + 1 if idx + 1 < len(scenario) else "END"
                    else :
                        scenario[idx]["FLOWS"][intent_name][idx_flow]["NEXT_ACTION"] = idx
        return scenario
    
    def set_questions(self, data: dict) -> None:
        if data.get("QUESTION"):
            max_loop = self.parsing(
                text=data.get("MAX_LOOP") if data.get("MAX_LOOP") else 2,
                typeofvalue="int",
            )
            value = {
                "TITLE": data.get("QUESTION"),
                "FLOWS": {},
                "MAX_LOOP": max_loop if isinstance(max_loop, int) else 100
            }
            return True, value
        return False, None

    
    def set_flow_with_intent_name(self, flow: dict, data: dict, pre_data: dict) -> None:
        intent_name = data.get("INTENT_NAME") if data.get("INTENT_NAME") else pre_data.get("INTENT_NAME")
        intent_description = data.get("INTENT_DESCRIPTION") if data.get("INTENT_DESCRIPTION") else pre_data.get("INTENT_DESCRIPTION")

        if flow.get("FLOWS").get(intent_name) is None:
            flow["FLOWS"][intent_name] = []
        flow["FLOWS"][intent_name].append(
            {
                "RESPONSE": self.get_reponse(data=data),
                "TOOL": self.get_tool(data=data),
                "INTENT_DESCRIPTION": intent_description,
                "REGEX_POSITIVE": self.get_regex_positive(data=data),
                "REGEX_NEGATIVE": self.get_regex_negative(data=data),
                "NEXT_ACTION": None,
                "LLM_ANSWERING": self.get_llm_answering(data=data),
                "SCORE": self.get_score(data=data),
                "MOOD": self.get_mood(data=data),
                "IMAGE": self.get_image(data=data),
                "VIDEO": self.get_video(data=data),
                "MOODS": self.get_moods(data=data),
                "LISTENING_ANIMATIONS": self.get_listening_aninimations(data=data),
                "LANGUAGE": self.get_language(data=data),
                "VOICE_SPEED": self.get_voice_speed(data=data),
                "VOLUME": self.get_volume(data=data),
                "TEXT_VIEWER": self.get_text_viewer(data=data),
                "BUTTON": self.get_button(data=data),
                "TRIGGER": self.get_trigger(data=data),
                "AUDIO_LISTENING": self.get_audio_listening(data=data),
                "IMAGE_LISTENING": self.get_image_listening(data=data),
            }
        )
        return flow

    def get_reponse(self, data: dict) -> List[str]:
        responses = []
        for key, value in data.items():
            if isinstance(key, str) and key.find("RESPONSE_") == 0:
                if value:
                    responses.append(value)
        if len(responses) == 0:
            responses.append("")
        return responses
    
    def get_tool(self, data: dict) -> List[str]:
        array_tool = []
        for key, value in data.items():
            if isinstance(key, str) and key[-5:] == "_TOOL" and isinstance(value, dict):
                array_tool.append({
                    "key": key,
                    "value": value,
                })
        return array_tool
    
    def get_loop_count(self, data: dict) -> List[str]:
        return data.get("LOOP_COUNT")
    
    def get_regex_positive(self, data: dict) -> List[str]:
        regex_positive = data.get("REGEX_POSITIVE")
        if regex_positive:
            return regex_positive.split("\n")
        return []
    
    def get_regex_negative(self, data: dict) -> List[str]:
        regex_negative = data.get("REGEX_NEGATIVE")
        if regex_negative:
            return regex_negative.split("\n")
        return []
    
    def get_llm_answering(self, data: dict) -> str:
        return data.get("LLM_ANSWERING")
    
    def get_score(self, data: dict) -> float:
        return self.parsing(data.get("SCORE"), typeofvalue="float")
    
    def get_mood(self, data: dict) -> str:
        return data.get("MOOD") if data.get("MOOD") else ""
    
    def get_image(self, data: dict) -> str:
        return data.get("IMAGE") if data.get("IMAGE") else ""
    
    def get_video(self, data: dict) -> str:
        return data.get("VIDEO") if data.get("VIDEO") else ""
    
    def get_moods(self, data: dict) -> str:
        return self.parsing(data.get("MOODS"), typeofvalue="json")
    
    def get_listening_aninimations(self, data: dict) -> str:
        return self.parsing(data.get("LISTENING_ANIMATIONS"), typeofvalue="json")
    
    def get_language(self, data: dict) -> str:
        return data.get("LANGUAGE") if data.get("LANGUAGE") else ""
    
    def get_voice_speed(self, data: dict) -> float:
        return self.parsing(data.get("VOICE_SPEED"), typeofvalue="float")

    def get_button(self, data: dict) -> str:
        return data.get("BUTTON") if data.get("BUTTON") else ""
    
    def get_trigger(self, data: dict) -> str:
        return self.parsing(data.get("TRIGGER"), typeofvalue="json")
    
    def get_audio_listening(self, data: dict) -> str :
        return data.get("AUDIO_LISTENING") if data.get("AUDIO_LISTENING") else ""
    
    def get_image_listening(self, data: dict) -> str :
        return data.get("IMAGE_LISTENING") if data.get("IMAGE_LISTENING") else ""
    
    def get_volume(self, data: dict) -> float:
        volume = data.get("VOLUME")
        if volume is not None:
            try:
                volume_float = float(volume)
                if -10 <= volume_float <= 10:
                    return volume_float
            except ValueError:
                pass
        return None
    
    def get_text_viewer(self, data: dict) -> str:
        return data.get("TEXT_VIEWER") if data.get("TEXT_VIEWER") else ""
    
    def get_list_intent(self, scenario: dict, cur_state: int) -> List[dict]:
        if not isinstance(cur_state, int) or cur_state >= len(scenario):
            return []
        state = scenario[cur_state]
        dict_intents = []
        if isinstance(state.get("FLOWS"), dict):
            for intent_name, value in state.get("FLOWS").items():
                intent_description = value[0].get("INTENT_DESCRIPTION")
                intent_description = intent_description if intent_description is not None else ""
                if intent_name == "silence":
                    continue
                dict_intents.append({
                    "intent_name": intent_name,
                    "intent_description": intent_description,
                })
        return dict_intents
    
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
    
    def parsing(self, text: str, typeofvalue: str):
        try :
            if not text:
                return None
            if typeofvalue == "int":
                return int(text)
            if typeofvalue == "float":
                return float(text)
            if typeofvalue == "json":
                if not text:
                    return None
                return json.loads(text)
            return None
        except:
            return None
    
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
            # response = requests.request("POST", url, headers=headers, data=json.dumps(payload, ensure_ascii=False))
            # result = response.json()
            # if isinstance(result, dict):
            #     if result.get('status') == 0 and result.get("result") is not None:
            #         return result.get("result")
            # return None
            # Sử dụng aiohttp để gửi POST request
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
        
    def norm_data_excel_with_intent_name_and_description(self, data: List[dict]):
        try :
            if not isinstance(data, list):
                return data
            data_excel = copy.deepcopy(data)
            output = []
            INTENT_NAME = ""
            INTENT_DESCRIPTION = ""
            for item in data_excel:
                if item.get("QUESTION"):
                    output.append(item)
                else :
                    if not item.get("INTENT_NAME") and not item.get("INTENT_DESCRIPTION"):
                        item["INTENT_NAME"] = INTENT_NAME
                        item["INTENT_DESCRIPTION"] = INTENT_DESCRIPTION
                    output.append(item)
                INTENT_NAME = item.get("INTENT_NAME")
                INTENT_DESCRIPTION = item.get("INTENT_DESCRIPTION")
            return output
        except:
            logging.info(f"[ERROR] update_data_from_profile: {traceback.format_exc()}")
            return data

    def get_answer_mode_from_scenario(self, scenario: list, idx: int):
        if not isinstance(scenario, list) or not isinstance(idx, int):
            return "RECORDING"
        if idx >= len(scenario):
            return "RECORDING"
        
        button_list = []
        for intent_name, item in scenario[idx].get("FLOWS").items():
            for value in item:
                if value.get("BUTTON") and value.get("BUTTON") not in button_list:
                    button_list.append(value.get("BUTTON"))
        if len(button_list) == 0:
            return "RECORDING"
        if len(button_list) == 3:
            return "BUTTON_3"
        if len(button_list) == 2:
            return "BUTTON_2"
        return "RECORDING"


    def get_gifs_from_scenario(self, scenario: List[dict]):
        try:
            if not isinstance(scenario, list):
                return []
            gif_list = []
            for flow in scenario:
                for intent_name, item in flow.get("FLOWS").items():
                    for value in item:
                        if value.get("IMAGE_LISTENING") and value.get("IMAGE_LISTENING") not in gif_list:
                            gif_list.append(value.get("IMAGE_LISTENING"))
                        if value.get("IMAGE") and value.get("IMAGE") not in gif_list:
                            gif_list.append(value.get("IMAGE"))
                        for response in value.get("RESPONSE"):
                            if isinstance(response, list):
                                for response_item in response:
                                    if response_item.get("image") and response_item.get("image") not in gif_list:
                                        gif_list.append(response_item.get("image"))
            return gif_list
        except:
            logging.info(f"[ERROR] get_gifs_from_scenario: {traceback.format_exc()}")
            return []
    
    def get_tool_recording_from_scenario(self, scenario: List[dict]):
        try:
            if not isinstance(scenario, list):
                return {}
            tool_recording = {}
            for idx, flow in enumerate(scenario):
                for intent_name, item in flow.get("FLOWS").items():
                    for value in item:
                        if  isinstance(value.get("TOOL"), list) and len(value.get("TOOL")) > 0:
                            for tool in value.get("TOOL"):
                                if tool_recording.get(tool.get("key")) is None:
                                    tool_recording[tool.get("key")] = {}
                                tool_recording[tool.get("key")][idx] = {
                                    "result": [],
                                }
            return tool_recording
        except:
            logging.info(f"[ERROR] get_tool_recording_from_scenario: {traceback.format_exc()}")
            return {}
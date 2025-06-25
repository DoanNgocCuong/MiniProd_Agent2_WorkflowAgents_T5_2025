import os, copy, random, json, aiohttp, asyncio
import hashlib
from typing import List
from .prompt import (
    SYSTEM_PROMPT, 
    format_prompt_from_variable, 
    get_system_conversation_history, 
    SYSTEM_PROMPT_EXTRACTIONS, 
    SYSTEM_PROMPT_LLM_ANSWERING,
    SYSTEM_PROMPT_EXTRACTION_PROFILE,
)
from .llm_base import BaseLLM
from .scenario import ScenarioExcel
import logging, traceback, time
from src.tools.tool_interface import ToolInterface
from src.channel.redis_client import RedisClient
from src.channel.rabbitmq_client import RabbitMQClient
from .regex_classifier import RegexIntentClassifier
from src.utils.utils import get_task_id 


INTENT_FALLBACK = os.getenv("INTENT_FALLBACK") if os.getenv("INTENT_FALLBACK") is not None else "fallback"
URL_WORKFLOW = os.getenv("URL_WORKFLOW") if os.getenv("URL_WORKFLOW") is not None else ""
URL_AGENT = os.getenv("URL_AGENT") if os.getenv("URL_AGENT") is not None else ""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class PoliciesWorkflow:

    def __init__(self):
        self.error_message = "Hệ thống lỗi"
        self.scenario_flow = ScenarioExcel()
        self.tool_interface = ToolInterface()
        self.redis_client = RedisClient(
            host=os.getenv("REDIS_HOST"),
            port=os.getenv("REDIS_PORT"),
            password=os.getenv("REDIS_PASSWORD")
        )
        self.rabbitmq_client = RabbitMQClient(
            host=os.getenv("RABBITMQ_HOST"),
            port=os.getenv("RABBITMQ_PORT"),
            username=os.getenv("RABBITMQ_USERNAME"),
            password=os.getenv("RABBITMQ_PASSWORD"),
            exchange=os.getenv("RABBITMQ_EXCHANGE"),
            queue_name=os.getenv("RABBITMQ_QUEUE"),
        )
        self.regex_classifier = RegexIntentClassifier()

    
    def fill_slot_to_answer_list(self, answer_list: List[dict], input_slots: dict, cur_action: dict) -> List[dict]:
        if isinstance(answer_list, str):
            answer_list = self.scenario_flow.norm_start_message_dict(answer_list, cur_action=cur_action)
        output = []
        for idx, answer in enumerate(answer_list):
            answer = self.scenario_flow.format_text_from_input_slots(
                input_slots=input_slots,
                text=answer.get("text"),
            )
            answer_list[idx]["text"] = answer
        return answer_list
    

    def get_text_answer(self, answer_list: List[dict]) -> str:
        if isinstance(answer_list, str):
            return answer_list
        if isinstance(answer_list, list) and len(answer_list) > 0:
            return " ".join([answer.get("text") if answer.get("text") is not None else ""  if isinstance(answer, dict) else answer for answer in answer_list])
        return ""

    
    async def process(self, 
        scenario: dict, 
        message: str, 
        record: dict, 
        params: dict,
        input_slots: dict,
        llm_base: BaseLLM, 
        conversation_id: str = None,
        is_tool: bool = False,
        audio_url: str = None,
        **kwargs) -> str:
        
        record_new = copy.deepcopy(record)
        logging.info(f"====================={conversation_id}: is_tool: {is_tool} - record_new.get('TOOL'): {record_new.get('TOOL')}")
        if is_tool != True and isinstance(record_new.get("TOOL"), dict) and isinstance(record_new.get("TOOL").get("TOOL_RESPONSE"), dict) and record_new.get("TOOL").get("TOOL_RESPONSE").get("status") == "CHAT":
            tool_name = record_new.get("TOOL").get("TOOL_NAME")
            tool_setting = record_new.get("TOOL").get("TOOL_SETTING")
            tool_conversation_id = record_new.get("TOOL").get("TOOL_CONVERSATION_ID")
            transitional_sentence = copy.deepcopy(tool_setting.get("transitional_sentence"))

            transitional_sentence = self.scenario_flow.format_text_from_input_slots(
                input_slots=copy.deepcopy(input_slots),
                text=transitional_sentence,
            )
            transitional_sentence = self.scenario_flow.norm_start_message_dict(transitional_sentence)[0]

            res_webhook_tool = await self.async_webhook(
                conversation_id=tool_conversation_id,
                robot_type=tool_setting.get("robot_type"),
                message=message,
            )
            if isinstance(res_webhook_tool, dict):
                logging.info(f"[WEBHOOK][TOOL]================: {res_webhook_tool}")
                record_new["TOOL"]["TOOL_RESPONSE"] = res_webhook_tool

                answer = res_webhook_tool.get("text")
                status = res_webhook_tool.get("status")
                record_new["ANSWER_MODE_TOOL"] = copy.deepcopy(res_webhook_tool.get("record").get("ANSWER_MODE"))

                next_action_step = record_new.get("NEXT_ACTION") if isinstance(record_new.get("NEXT_ACTION"), int) else len(scenario)
                if isinstance(res_webhook_tool.get("record"), dict) and isinstance(res_webhook_tool.get("record").get("TOOL"), dict) and res_webhook_tool.get("record").get("TOOL").get("TOOL_NAME"):
                    tool = res_webhook_tool.get("record").get("TOOL")
                    if isinstance(record_new.get("TOOL_RECORDING"), dict) and isinstance(record_new.get("TOOL_RECORDING").get(tool.get("TOOL_NAME")), dict) \
                        and isinstance(record_new.get("TOOL_RECORDING").get(tool.get("TOOL_NAME")).get(str(next_action_step-1)), dict):
                        record_new["TOOL_RECORDING"][tool.get("TOOL_NAME")][str(next_action_step-1)]["result"].append(tool.get("TOOL_RESULT"))

                if status in ["END", "ERROR"]:
                    record_new["ANSWER_MODE_TOOL"] = None
                    record_new["LANGUAGE"] = record_new.get("LANGUAGE_SOURCE") if record_new.get("LANGUAGE_SOURCE") else ""
                    if isinstance(answer, list):
                        answer.append(transitional_sentence)
                    else :
                        answer = [answer, transitional_sentence]
                    status = record_new.get("status")
                else :
                    record_new["LANGUAGE"] = copy.deepcopy(res_webhook_tool.get("record").get("LANGUAGE"))
                
                record_new["MOOD"] = res_webhook_tool.get("record").get("MOOD")
                record_new["IMAGE"] = res_webhook_tool.get("record").get("IMAGE")
                record_new["VIDEO"] = res_webhook_tool.get("record").get("VIDEO")
                record_new["MOODS"] = res_webhook_tool.get("record").get("MOODS")
                record_new["LISTENING_ANIMATIONS"] = res_webhook_tool.get("record").get("LISTENING_ANIMATIONS")
                record_new["VOICE_SPEED"] = res_webhook_tool.get("record").get("VOICE_SPEED")
                record_new["VOLUME"] = res_webhook_tool.get("record").get("VOLUME")
                record_new["TEXT_VIEWER"] = res_webhook_tool.get("record").get("TEXT_VIEWER")
                record_new["AUDIO_LISTENING"] = res_webhook_tool.get("record").get("AUDIO_LISTENING")
                record_new["IMAGE_LISTENING"] = res_webhook_tool.get("record").get("IMAGE_LISTENING")
                # record_new["TRIGGER"] = res_webhook_tool.get("record").get("TRIGGER")
                return status, answer, record_new

        pre_action = record_new.get("CUR_ACTION")
        messages = self.preprocess_messages(
            message=message, 
            pre_action=pre_action, 
            history_question=record.get("HISTORY_QUESTION"), 
            **kwargs
        )
        variables = copy.deepcopy(input_slots)
        if kwargs.get("history") not in [None, ""] and isinstance(kwargs.get("question_idx"), int):
            record["NEXT_ACTION"] = int(kwargs.get("question_idx"))
        dict_intents = self.scenario_flow.get_list_intent(
            scenario=scenario,
            cur_state=record.get("NEXT_ACTION")
        )
        variables.update(
            {
                "SYSTEMT_INTENT_DESCRIPTION" : json.dumps(dict_intents, ensure_ascii=False, indent=4)
            }
        )
        messages = format_prompt_from_variable(prompt=messages, variables=variables)

        ## PUSH TASK IN QUEUE
        start_time = time.time()
        self.push_task_to_queue(
            conversation_id=conversation_id,
            message=message,
            audio_url=audio_url,
            scenario=scenario,
            record=record_new,
            input_slots=input_slots,
            is_tool=is_tool,
        )

        intent_llm = None
        if record.get("NEXT_ACTION") > 0:
            if message in [None, "", "silence", "<silence>", " "]:
                intent_llm = "silence"
            else :
                intent_llm = self.regex_classifier.button_click_classifier(
                    message=message,
                    scenario=scenario,
                    next_action=record.get("NEXT_ACTION")
                )
                if not intent_llm:
                    intent_llm = self.regex_classifier.process(
                        message=message,
                        scenario=scenario,
                    next_action=record.get("NEXT_ACTION")
                )
                if not intent_llm:
                    intent_llm = await llm_base.predict(
                        messages=messages,
                        params=params,
                        conversation_id=conversation_id,
                        **kwargs
                    )
            cur_intent = intent_llm
        else :
            cur_intent = INTENT_FALLBACK
        state, cur_action, cur_intent = self.workflow(
            scenario=scenario,
            cur_intent=cur_intent,
            record=record_new,
        )
        logging.info(f"[WORKFLOW][process]====================={conversation_id}: cur_action: {cur_action}")

        if len(cur_action.get("TOOL")) == 0 and is_tool == True:
            record_new["TOOL"]["TOOL_NAME"] = None
            record_new["TOOL"]["TOOL_RESULT"] = None
            record_new["TOOL"]["TOOL_SETTING"] = None
            record_new["TOOL"]["TOOL_CONVERSATION_ID"] = None
            record_new["TOOL"]["TOOL_RESPONSE"] = None
        if len(cur_action.get("TOOL")) > 0 and is_tool == True and cur_action.get("TOOL")[0].get("key") == "PRONUNCIATION_CHECKER_TOOL":
            tool = copy.deepcopy(cur_action.get("TOOL")[0])
            if isinstance(tool, dict) and isinstance(tool.get("value"), dict):
                tool["value"]["text_refs"] = input_slots.get("TARGET_ANSWER")
            task_id = self.get_task_id_from_tool(
                conversation_id=conversation_id,
                tool=tool,
            )
            tool_res = self.redis_client.get(task_id)
            while time.time() - start_time < 3 and tool_res is None:
                tool_res = self.redis_client.get(task_id)
                if tool_res is None:
                    await asyncio.sleep(0.1)
            tool_res = self.parsing_json(tool_res)
            if isinstance(tool_res, dict) and len(tool_res) > 0 and isinstance(tool_res.get("TOOL_RESULT"), dict):
                record_new["TOOL"]["TOOL_RESULT"] = tool_res.get("TOOL_RESULT")
                record_new["TOOL"]["TOOL_NAME"] = tool_res.get("TOOL_NAME")
                # next_action = record_new.get("NEXT_ACTION") if isinstance(record_new.get("NEXT_ACTION"), int) else len(scenario)
                # logging.info(f"=================================next_action: {next_action} - {isinstance(record_new.get('TOOL_RECORDING'), dict)} - {isinstance(record_new.get('TOOL_RECORDING').get(tool.get('key')), dict)} - {isinstance(record_new.get('TOOL_RECORDING').get(tool.get('key')).get(str(next_action-1)), dict)}")
                # if isinstance(record_new.get("TOOL_RECORDING"), dict) and isinstance(record_new.get("TOOL_RECORDING").get(tool.get("key")), dict) \
                #     and isinstance(record_new.get("TOOL_RECORDING").get(tool.get("key")).get(str(next_action-1)), dict):
                #     record_new["TOOL_RECORDING"][tool.get("key")][str(next_action-1)]["result"].append(tool_res.get("TOOL_RESULT"))

            if isinstance(tool_res, dict) and len(tool_res) > 0 and isinstance(tool_res.get("TOOL_RESULT"), dict) and tool_res.get("TOOL_RESULT").get("feedback") not in [None, ""]:
                cur_intent = INTENT_FALLBACK
                state, cur_action, cur_intent = self.workflow(
                    scenario=scenario,
                    cur_intent=cur_intent,
                    record=record_new,
                )
                
        status = "CHAT"
        if isinstance(cur_action, dict) and cur_action.get("NEXT_ACTION") == "END":
            status = "END"
        if state == "ERROR":
            status = "END"

        if not isinstance(cur_action, dict):
            next_action = -1
            answer = cur_action
        else :
            next_action = cur_action.get("NEXT_ACTION")
            if str(cur_action.get("LLM_ANSWERING")).upper() == "TRUE":
                answer = await self.get_llm_answering(
                    pre_action=record.get("CUR_ACTION"),
                    message=message,
                    target_action="say goodbye and end conversation" if next_action in ["END", "ERRROR"] else scenario[next_action].get("TITLE"),
                    llm_base=llm_base,
                    params=params,
                )
            else :
                answer = self.get_actions(
                    cur_action=cur_action
                )

        ## UPDATE RECORD
        pre_state = copy.deepcopy(record_new.get("NEXT_ACTION"))
        record_new["status"] = status
        if record_new.get("LOOP_COUNT")[pre_state].get(cur_intent) is None:
            record_new.get("LOOP_COUNT")[pre_state][cur_intent] = 0
        record_new.get("LOOP_COUNT")[pre_state][cur_intent] += 1
        record_new["NEXT_ACTION"] = next_action
        record_new["PRE_ACTION"] = record.get("CUR_ACTION")
        record_new["CUR_INTENT"] = cur_intent
        record_new["INTENT_PREDICT_LLM"] = intent_llm
        record_new["SYSTEM_SCORE_SUM"] += self.get_score_addition(cur_action.get("SCORE"))
        record_new["MOOD"] = cur_action.get("MOOD")
        record_new["IMAGE"] = cur_action.get("IMAGE")
        record_new["VIDEO"] = cur_action.get("VIDEO")
        record_new["MOODS"] = cur_action.get("MOODS")
        record_new["LISTENING_ANIMATIONS"] = cur_action.get("LISTENING_ANIMATIONS")
        record_new["LANGUAGE"] = cur_action.get("LANGUAGE")
        record_new["VOICE_SPEED"] = cur_action.get("VOICE_SPEED")
        record_new["VOLUME"] = cur_action.get("VOLUME")
        record_new["TEXT_VIEWER"] = cur_action.get("TEXT_VIEWER")
        record_new["AUDIO_LISTENING"] = cur_action.get("AUDIO_LISTENING")
        record_new["IMAGE_LISTENING"] = cur_action.get("IMAGE_LISTENING")
        record_new["TRIGGER"] = cur_action.get("TRIGGER")
        variables.update(
            copy.deepcopy(record_new)
        )
        answer = self.fill_slot_to_answer_list(
            answer_list=answer,
            cur_action=cur_action,
            input_slots=variables,
        )

        # if is_tool == False:
        #     ## ANSWER MEMORY
        #     task_id = get_task_id(
        #         bot_id=kwargs.get("bot_id"),
        #         conversation_id=conversation_id,
        #         input_string=answer,
        #     )
        #     answer_memory = self.redis_client.get(task_id)
        #     logging.info(f"============[ANSWER MEMORY] - {task_id} - {answer} - answer_memory: {answer_memory}")
        #     if answer_memory not in [None, "PROCESSING", "END", ""]:
        #         answer_memory = self.parsing_json(answer_memory)
        #         if isinstance(answer_memory, dict) and answer_memory.get("status") == 200:
        #             answer = answer_memory.get("result")
        #     ## END ANSWER MEMORY

        #     task_answers = self.get_answer_next_predict(
        #         scenario=scenario,
        #         idx=next_action,
        #     )
        #     self.push_memory_answer(
        #         conversation_id=conversation_id,
        #         bot_id=kwargs.get("bot_id"),
        #         answers=task_answers,
        #         user_id=kwargs.get("user_id"),
        #         variables=variables,
        #     )

        record_new["CUR_ACTION"] = self.get_text_answer(answer)
        if isinstance(record_new.get("HISTORY_QUESTION"), list):
            if next_action != record["NEXT_ACTION"]:
                record_new["HISTORY_QUESTION"] = [
                    {
                        "role": "assistant",
                        "content": self.get_text_answer(answer)
                    }
                ]
        ## END RECORD
        if isinstance(cur_action.get("TOOL"), list) and len(cur_action.get("TOOL")) > 0 and is_tool == False:
            for tool in cur_action.get("TOOL"):
                task_id = self.get_task_id_from_tool(
                    conversation_id=conversation_id,
                    tool=tool,
                )
                tool_res = self.redis_client.get(task_id)
                while time.time() - start_time < 3 and tool_res is None:
                    tool_res = self.redis_client.get(task_id)
                    if tool_res is None:
                        await asyncio.sleep(0.1)
                logging.info(f"[TOOL][CALL TOOL] CALL TOOL FINISHED================next_action: {next_action} - tool_res: {tool_res}")
                tool_res = self.parsing_json(tool_res)
                if isinstance(tool_res, dict) and len(tool_res) > 0 and isinstance(tool_res.get("TOOL_RESULT"), dict):
                    record_new["TOOL"]["TOOL_NAME"] = tool_res.get("TOOL_NAME")
                    record_new["TOOL"]["TOOL_RESULT"] = tool_res.get("TOOL_RESULT")
                    record_new["TOOL"]["TOOL_SETTING"] = tool_res.get("TOOL_SETTING")
                    record_new["TOOL"]["TOOL_CONVERSATION_ID"] = tool_res.get("TOOL_CONVERSATION_ID")
                    next_action_step = len(scenario) if next_action == "END" else next_action
                    if isinstance(record_new.get("TOOL_RECORDING"), dict) and isinstance(record_new.get("TOOL_RECORDING").get(tool.get("key")), dict) \
                        and isinstance(record_new.get("TOOL_RECORDING").get(tool.get("key")).get(str(next_action_step-1)), dict):
                        record_new["TOOL_RECORDING"][tool.get("key")][str(next_action_step-1)]["result"].append(tool_res.get("TOOL_RESULT"))
                else :
                    continue
                if tool.get("key") == "PRONUNCIATION_CHECKER_TOOL" and tool.get('value', {}).get("intent_name") and tool_res.get("TOOL_RESULT").get("feedback"):
                    status, answer, record_new = await self.update_cur_action(
                        scenario=scenario,
                        cur_action=cur_action,
                        record_new=record_new,
                        intent_name=tool.get('value', {}).get("intent_name"),
                        variables=variables,
                        pre_state=pre_state,
                        record=record,
                        intent_llm=intent_llm,
                    )
                    break
                if (tool_res.get("TOOL_NAME") == "PRONUNCIATION_CHECKER_TOOL" and tool_res.get("TOOL_RESULT").get("feedback") not in [None, ""]) \
                    or (tool_res.get("TOOL_NAME") == "GRAMMAR_CHECKER_TOOL" and tool_res.get("TOOL_RESULT").get("explanation") not in [None, ""]):
                    tool_name = tool_res.get("TOOL_NAME")
                    tool_result = tool_res.get("TOOL_RESULT")
                    tool_conversation_id = tool_res.get("TOOL_CONVERSATION_ID")
                    tool_setting = tool_res.get("TOOL_SETTING")
                    if tool_name == "PRONUNCIATION_CHECKER_TOOL":
                        START_MESSAGE = tool_result.get("feedback")
                        TARGET_ANSWER = tool_result.get("target")
                    else :
                        START_MESSAGE = tool_result.get("explanation")
                        TARGET_ANSWER = tool_result.get("fixed_answer")
                    init_status = await self.async_init_conversation(
                        conversation_id=tool_conversation_id,
                        robot_type=tool_setting.get("robot_type"),
                        robot_type_id=tool_setting.get("robot_type_id"),
                        input_slots={
                            "START_MESSAGE": START_MESSAGE,
                            "TARGET_ANSWER": TARGET_ANSWER,
                        },
                        is_tool=True,
                    )
                    logging.info(f"[INIT CALL]================: {init_status}")
                    if init_status == True:
                        res_webhook_tool = await self.async_webhook(
                            conversation_id=tool_conversation_id,
                            robot_type=tool_setting.get("robot_type"),
                            message=message,
                            first_message=message,
                        )
                        logging.info(f"[WEBHOOK][TOOL]================: {res_webhook_tool}")
                        if isinstance(res_webhook_tool, dict):
                            record_new["MOOD"] = res_webhook_tool.get("record").get("MOOD")
                            record_new["IMAGE"] = res_webhook_tool.get("record").get("IMAGE")
                            record_new["VIDEO"] = res_webhook_tool.get("record").get("VIDEO")
                            record_new["MOODS"] = res_webhook_tool.get("record").get("MOODS")
                            record_new["LISTENING_ANIMATIONS"] = res_webhook_tool.get("record").get("LISTENING_ANIMATIONS")
                            
                            record_new["VOICE_SPEED"] = res_webhook_tool.get("record").get("VOICE_SPEED")
                            record_new["VOLUME"] = res_webhook_tool.get("record").get("VOLUME")
                            record_new["TEXT_VIEWER"] = res_webhook_tool.get("record").get("TEXT_VIEWER")
                            
                            record_new["LANGUAGE_SOURCE"] = copy.deepcopy(record_new.get("LANGUAGE"))
                            record_new["LANGUAGE"] = copy.deepcopy(res_webhook_tool.get("record").get("LANGUAGE"))
                            record_new["AUDIO_LISTENING"] = copy.deepcopy(res_webhook_tool.get("record").get("AUDIO_LISTENING"))
                            record_new["IMAGE_LISTENING"] = copy.deepcopy(res_webhook_tool.get("record").get("IMAGE_LISTENING"))
                            record_new["ANSWER_MODE_TOOL"] = copy.deepcopy(res_webhook_tool.get("record").get("ANSWER_MODE"))
                            # record_new["TRIGGER"] = copy.deepcopy(res_webhook_tool.get("record").get("TRIGGER"))
                            record_new["TOOL"]["TOOL_RESPONSE"] = res_webhook_tool
                            answer = res_webhook_tool.get("text")
                            status = res_webhook_tool.get("status")
                    break
        else :
            if is_tool != True:
                record_new["TOOL"]["TOOL_NAME"] = None
                record_new["TOOL"]["TOOL_RESULT"] = None
                record_new["TOOL"]["TOOL_SETTING"] = None
                record_new["TOOL"]["TOOL_CONVERSATION_ID"] = None
                record_new["TOOL"]["TOOL_RESPONSE"] = None

        return status, answer, record_new

    
    async def update_cur_action(self, 
        scenario: dict, 
        cur_action: dict, 
        record_new: dict, 
        intent_name: str, 
        variables: dict, 
        pre_state: int,
        record: dict,
        intent_llm: str):

        record_new["NEXT_ACTION"] = record.get("NEXT_ACTION")
        state, cur_action, cur_intent = self.workflow(
            scenario=scenario,
            cur_intent=intent_name,
            record=record_new,
        )

        status = "CHAT"
        if isinstance(cur_action, dict) and cur_action.get("NEXT_ACTION") == "END":
            status = "END"
        if state == "ERROR":
            status = "END"

        if not isinstance(cur_action, dict):
            next_action = -1
            answer = cur_action
        else :
            next_action = cur_action.get("NEXT_ACTION")
            if str(cur_action.get("LLM_ANSWERING")).upper() == "TRUE":
                answer = await self.get_llm_answering(
                    pre_action=record.get("CUR_ACTION"),
                    message=message,
                    target_action="say goodbye and end conversation" if next_action in ["END", "ERRROR"] else scenario[next_action].get("TITLE"),
                    llm_base=llm_base,
                    params=params,
                )
            else :
                answer = self.get_actions(
                    cur_action=cur_action
                )

        ## UPDATE RECORD
        # pre_state = copy.deepcopy(record_new.get("NEXT_ACTION"))
        record_new["status"] = status
        if record_new.get("LOOP_COUNT")[pre_state].get(cur_intent) is None:
            record_new.get("LOOP_COUNT")[pre_state][cur_intent] = 0
        record_new.get("LOOP_COUNT")[pre_state][cur_intent] += 1
        record_new["NEXT_ACTION"] = next_action
        record_new["PRE_ACTION"] = record.get("CUR_ACTION")
        record_new["CUR_INTENT"] = cur_intent
        record_new["INTENT_PREDICT_LLM"] = intent_llm
        record_new["SYSTEM_SCORE_SUM"] += self.get_score_addition(cur_action.get("SCORE"))
        record_new["MOOD"] = cur_action.get("MOOD")
        record_new["IMAGE"] = cur_action.get("IMAGE")
        record_new["VIDEO"] = cur_action.get("VIDEO")
        record_new["MOODS"] = cur_action.get("MOODS")
        record_new["LISTENING_ANIMATIONS"] = cur_action.get("LISTENING_ANIMATIONS")
        record_new["LANGUAGE"] = cur_action.get("LANGUAGE")
        record_new["VOICE_SPEED"] = cur_action.get("VOICE_SPEED")
        record_new["VOLUME"] = cur_action.get("VOLUME")
        record_new["TEXT_VIEWER"] = cur_action.get("TEXT_VIEWER")
        record_new["AUDIO_LISTENING"] = cur_action.get("AUDIO_LISTENING")
        record_new["IMAGE_LISTENING"] = cur_action.get("IMAGE_LISTENING")
        record_new["TRIGGER"] = cur_action.get("TRIGGER")
        
        answer = self.fill_slot_to_answer_list(
            answer_list=answer,
            cur_action=cur_action,
            input_slots=variables,
        )
        record_new["CUR_ACTION"] = self.get_text_answer(answer)
        if isinstance(record_new.get("HISTORY_QUESTION"), list):
            if next_action != record["NEXT_ACTION"]:
                record_new["HISTORY_QUESTION"] = [
                    {
                        "role": "assistant",
                        "content": self.get_text_answer(answer)
                    }
                ]
        return status, answer, record_new

    def preprocess_messages(self, pre_action: str, message: str, history_question: list, **kwargs):
        if isinstance(kwargs.get("history"), list) and len(kwargs.get("history")) > 0:
            history = kwargs.get("history")
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT if kwargs.get("system_prompt") in [None, ""] else kwargs.get("system_prompt"),
                }
            ]
            messages.extend(history)
            messages.append({
                "role": "user",
                "content": message if message is not None else ""
            })
        else :
            if isinstance(history_question, list) and len(history_question) > 0:
                messages = [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT if kwargs.get("system_prompt") in [None, ""] else kwargs.get("system_prompt"),
                    }
                ]
                messages.extend(history_question)
                messages.append({
                    "role": "user",
                    "content": message if message is not None else ""
                })
            else :
                messages = [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT if kwargs.get("system_prompt") in [None, ""] else kwargs.get("system_prompt"),
                    },
                    {
                        "role": "assistant",
                        "content": pre_action if pre_action is not None else ""
                    },
                    {
                        "role": "user",
                        "content": message if message is not None else ""
                    }
                ]
        return messages
    

    def workflow(self, scenario: dict, cur_intent: str, record: dict, **kwargs):
        cur_state = record.get("NEXT_ACTION")
        if cur_state >= len(scenario):
            return "ERROR", self.error_message, cur_intent
        state = copy.deepcopy(scenario[cur_state])
        cur_action = None
        loop_count = record.get("LOOP_COUNT")[cur_state]
        if isinstance(state.get("FLOWS"), dict):
            if state.get("FLOWS").get(cur_intent) is None:
                cur_intent = INTENT_FALLBACK
            loop_count_full = [int(value) for key, value in loop_count.items()] if len(loop_count) > 0 else []
            if len(loop_count_full) > 0:
                loop_count_full = sum(loop_count_full)
            else :
                loop_count_full = 0
            repeat = loop_count.get(cur_intent) if isinstance(loop_count.get(cur_intent), int) else 0
            repeat += 1
            loop_count_full += 1
            if state.get("FLOWS").get(cur_intent) is not None:
                if isinstance(state.get("MAX_LOOP"), int) and loop_count_full >= state.get("MAX_LOOP"):
                    cur_action = state.get("FLOWS").get(cur_intent)[-1]
                else :
                    cur_action = state.get("FLOWS").get(cur_intent)[repeat - 1] if repeat - 1 < len(state.get("FLOWS").get(cur_intent)) else state.get("FLOWS").get(cur_intent)[-1]
            else :
                return "ERROR", self.error_message, cur_intent
        if cur_action is not None:
            # if idx
            return "SUCCESS", cur_action, cur_intent
        return "ERROR", self.error_message, cur_intent

    
    def get_actions(self, cur_action: dict) -> str:
        if not isinstance(cur_action, dict):
            return cur_action
        answers = random.sample(cur_action.get("RESPONSE"), 1)[0]
        return answers
    
    async def get_llm_answering(self, pre_action: str, message: str, target_action: str, llm_base: BaseLLM, params: dict):
        text_history = f"""
        Assistant: {pre_action}
        User: {message}
        Target Question: {target_action}
        """
        variables = {
            "SYSTEM_HISTORY_LLM_ANSWERING": text_history
        }
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT_LLM_ANSWERING,
            }
        ]
        messages = format_prompt_from_variable(prompt=messages, variables=variables)
        reponse = await llm_base.get_response(
            messages = messages,
            **params
        )
        return reponse

    async def run_extract_and_generation(self, 
        params: dict,
        input_slots: dict,
        system_extraction_variables: str,
        system_prompt_generation: str,
        history: str,
        llm_base: BaseLLM, 
        **kwargs
    ) -> dict :
        # async def run_param_extractor(self, task_chain, history, task_idx, llm_base, generation_params, system_context_variables):
        ## EXTRACTIION CONTEXT
        system_context_variables = {}
        
        conversation_history = get_system_conversation_history(history)
        context_variables = copy.deepcopy(input_slots)
        context_variables["SYSTEM_EXTRACTION_VARIABLES"] = system_extraction_variables
        context_variables["SYSTEM_CONVERSATION_HISTORY"] = conversation_history
        if system_extraction_variables not in ["", None]:
            history_context_variable = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT_EXTRACTIONS,
                },
                {
                    "role": "user",
                    "content": conversation_history
                }
            ]
            history_context_variable = format_prompt_from_variable(history_context_variable, context_variables)
            res_context_variable = await llm_base.get_response(
                messages = history_context_variable,
                **params,
            )
            res_context_variable = llm_base.parsing_json(res_context_variable)
            if isinstance(res_context_variable, dict):
                system_context_variables.update(res_context_variable)

        
        if system_prompt_generation not in ["", None]:
            history_prompt_generation = [
                {
                    "role": "system",
                    "content": system_prompt_generation,
                }
            ]
            history_prompt_generation = format_prompt_from_variable(history_prompt_generation, system_context_variables)
            res_context_generation = await llm_base.get_response(
                messages = history_prompt_generation,
                **params,
            )
            res_context_generation = llm_base.parsing_json(res_context_generation)
            # logging.info(f"============res_context_generation: {res_context_generation}")
            if isinstance(res_context_generation, dict):
                system_context_variables.update(res_context_generation)
        return system_context_variables
    
    def get_score_addition(self, score_text: str):
        if isinstance(score_text, int) or isinstance(score_text, float):
            return int(score_text)
        if isinstance(score_text, str):
            try :
                if score_text:
                    return int(float(score_text))
                return 0
            except:
                logging.info(f"[ERROR] Get Score Addition Error: {traceback.format_exc()}")
                return 0
        return 0
    
    def push_task_to_queue(self, 
        conversation_id: str, 
        message: str, 
        audio_url: str, 
        scenario: dict, 
        record: dict, 
        input_slots = {},
        is_tool = False,
        **kwargs):
        cur_state = record.get("NEXT_ACTION")
        if cur_state >= len(scenario):
            return
        state = copy.deepcopy(scenario[cur_state])
        list_tools = []
        for intent_name in state.get("FLOWS").keys():
            for action in state.get("FLOWS").get(intent_name):
                if isinstance(action.get("TOOL"), list) and len(action.get("TOOL")) > 0:
                    for tool in action.get("TOOL"):
                        if is_tool == True and tool.get("key") == "PRONUNCIATION_CHECKER_TOOL":
                            tool["value"]["text_refs"] = input_slots.get("TARGET_ANSWER")
                        if tool not in list_tools:
                            list_tools.append(tool)
        for tool in list_tools:
            if isinstance(tool, dict):
                task_id = self.get_task_id_from_tool(conversation_id, tool)
                self.redis_client.delete(task_id)
                self.rabbitmq_client.send_task(
                    message=json.dumps({
                        "conversation_id": conversation_id,
                        "tool": tool,
                        "message": message,
                        "audio_url": audio_url,
                        "task_id": task_id,
                    }, ensure_ascii=False),
                )

    def get_task_id_from_tool(self, conversation_id, tool: dict):
        return conversation_id + "-" + str(hashlib.sha256(json.dumps(tool, ensure_ascii=False).encode('utf-8')).hexdigest())

    async def run_tools(self, 
        conversation_id: str,
        tools: List[dict],
        message: str,
        audio_url: str,
        **kwargs
    ) -> dict :
        for element in tools:
            key = element.get("key")
            value = element.get("value")
            if not isinstance(value, dict):
                continue
            text_refs = value.get("text_refs")
            if key == "PRONUNCIATION_CHECKER_TOOL" and not text_refs:
                text_refs = message
            question = value.get("question")
            res = await self.tool_interface.process(
                conversation_id=conversation_id,
                tool_name=key,
                message=message,
                audio_url=audio_url,
                text_refs=text_refs,
                question=question,
                **kwargs
            )
            if isinstance(res, dict):
                return key, value, res
        return None, None, None
    

    async def async_init_conversation(self, conversation_id: str, robot_type: str, robot_type_id: int, input_slots: dict, is_tool = False, **kwargs):
        try :
            headers = {'Content-Type': 'application/json'}
            url = None
            if robot_type == "WORKFLOW":
                url = URL_WORKFLOW
            elif robot_type == "AGENT":
                url = URL_AGENT
            payload = {
                "bot_id": robot_type_id,
                "conversation_id": conversation_id,
                "input_slots": input_slots if isinstance(input_slots, dict) else {},
                "is_tool": is_tool,
            }
            logging.info(f"[INIT CALL]================: {url}/initConversation - {payload}")
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{url}/initConversation", json=payload, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        result = await response.json()
                        if isinstance(result, dict) and result.get("status") == 0:
                            return True
            return False
        except Exception as e:
            logging.info(f"[ERROR] async_init_conversation: {traceback.format_exc()}")
            return False
    

    async def async_webhook(self, conversation_id: str, robot_type: str, message: str, first_message: str = None, **kwargs):
        try :
            headers = {'Content-Type': 'application/json'}
            url = None
            if robot_type == "WORKFLOW":
                url = URL_WORKFLOW
            elif robot_type == "AGENT":
                url = URL_AGENT

            if first_message is not None:
                payload = {
                    "conversation_id": conversation_id,
                    "message": message,
                    "first_message": first_message
                }
            else :
                payload = {
                    "conversation_id": conversation_id,
                    "message": message
                }

            logging.info(f"[WEBHOOK]================: {url}/webhook - {payload}")
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{url}/webhook", json=payload, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        result = await response.json()
                        if isinstance(result, dict):
                            return result
            return None
        except Exception as e:
            logging.info(f"[ERROR] async_webhook: {traceback.format_exc()}")
            return None
    
    def parsing_json(self, text: str):
        try:
            if text in [None, ""]:
                return text
            return json.loads(text)
        except:
            return text
        
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
    
    def get_answer_next_predict(self, scenario: dict, idx: int) -> List[str]:
        try :
            if idx >= len(scenario):
                return []
            state = scenario[idx]
            list_answer = []
            if isinstance(state.get("FLOWS"), dict):
                for _, value in state.get("FLOWS").items():
                    if isinstance(value, list):
                        for action in value:
                            if isinstance(action.get("RESPONSE"), list):
                                list_answer.extend(action.get("RESPONSE"))
            return list_answer
        except:
            logging.info(f"[ERROR] get_answer_next_predict: {traceback.format_exc()}")
            return []
    
    
    def push_memory_answer(self, conversation_id: str, bot_id: str, answers: List[str], history: List[dict] = None, user_id: str = None, variables: dict = {}):
        try :
            for answer in copy.deepcopy(answers):
                answer =self.scenario_flow.format_text_from_input_slots(
                    input_slots=variables,
                    text=answer
                )
                task_id = get_task_id(
                    bot_id=bot_id,
                    conversation_id=conversation_id,
                    input_string=answer,
                )
                if self.redis_client.get(task_id) is None and user_id is not None:
                    self.redis_client.set(task_id, "PROCESSING", expire_time=5 * 60)
                    self.rabbitmq_client.send_task(
                        message=json.dumps(
                            {
                                "task_name": "PIKA_MEMORY",
                                "conversation_id": conversation_id,
                                "task_id": task_id,
                                "user_id": user_id,
                                "bot_id": bot_id,
                                "history": [
                                    {
                                        "role": "assistant",
                                        "content": answer
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    )
        except:
            logging.info(f"[ERROR] push_memory_answer: {traceback.format_exc()}")


    def caculate_tool_recording(self, record_new: dict):
        if isinstance(record_new.get("TOOL_RECORDING"), dict) and isinstance(record_new.get("TOOL_RECORDING").get("PRONUNCIATION_CHECKER_TOOL"), dict) and len(record_new.get("TOOL_RECORDING").get("PRONUNCIATION_CHECKER_TOOL")) > 0:
            count_success = 0
            for _, tool_step_value in record_new.get("TOOL_RECORDING").get("PRONUNCIATION_CHECKER_TOOL").items():
                if isinstance(tool_step_value.get("result"), list) and len(tool_step_value.get("result")) > 0:
                    if not tool_step_value.get("result")[0].get("feedback"):
                        count_success += 1
            if record_new.get("TOOL_SCORE") is None:
                record_new["TOOL_SCORE"] = {}
            if record_new.get("TOOL_SCORE").get("PRONUNCIATION_CHECKER_TOOL") is None:
                record_new["TOOL_SCORE"]["PRONUNCIATION_CHECKER_TOOL"] = {}
            record_new["TOOL_SCORE"]["PRONUNCIATION_CHECKER_TOOL"]["SCORE"] = count_success / len(record_new.get("TOOL_RECORDING").get("PRONUNCIATION_CHECKER_TOOL"))
        return record_new

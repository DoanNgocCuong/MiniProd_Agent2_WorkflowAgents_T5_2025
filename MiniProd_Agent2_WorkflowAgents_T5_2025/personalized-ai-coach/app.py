from fastapi import FastAPI, Request
from pydantic import BaseModel
import asyncio
import os, logging, uuid
import random
import string, json, re
import uvicorn
from typing import List, Optional, Union
import argparse, yaml, copy
from datetime import datetime
import traceback, yaml
from typing import Any
import string, json
import uvicorn
from typing import List, Optional, Union
import argparse, yaml, copy, time
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.utils.utils import get_provider, load_llm_bot_config, init_llm_bot_config, parsing_json, async_init_conversation, async_webhook
from src.channel.mysql_bot import LLMBot
from src.channel.redis_client import RedisClient
from src.chatbot.pipeline_task import PipelineTask
from src.tools.tool_config import TOOL_OBJECTS
from src.chatbot.prompt import format_prompt_from_variable, format_text_from_input_slots
from src.tools.user_profile import UserProfile
from src.channel.rabbitmq_client import RabbitMQClient


logging.getLogger("pika").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


parser = argparse.ArgumentParser()

parser.add_argument("--host", type=str, help="Host of API", default="127.0.0.1")
parser.add_argument("--port", type=int, help="Port of API", default=9330)
parser.add_argument("--workers", type=int, help="Port of API", default=1)

parser.add_argument("--redis_host", type=str, help="Host of Redis", default="callbot-llm-redis")
parser.add_argument("--redis_port", type=int, help="Port of Redis", default=6379)
parser.add_argument("--redis_password", type=str, help="password of Redis", default="123456aA@")

parser.add_argument("--mysql_host", type=str, help="Host of mysql", default="callbot-llm-mysql")
parser.add_argument("--mysql_port", type=int, help="Port of mysql", default=3306)
parser.add_argument("--mysql_username", type=str, help="Username of mysql", default="root")
parser.add_argument("--mysql_password", type=str, help="password of mysql", default="123456aA@")
parser.add_argument("--mysql_database", type=str, help="database of mysql", default="callbot_llm")

args = parser.parse_args()

REDIS_CLIENT = RedisClient(
    host=args.redis_host,
    port=args.redis_port,
    password=args.redis_password,
)

LLMBOT_DATABSE = LLMBot(
    host=args.mysql_host,
    port=args.mysql_port,
    username=args.mysql_username,
    password=args.mysql_password,
    database=args.mysql_database,
)

RABBIT_CLIENT = RabbitMQClient(
    host=os.getenv("RABBITMQ_HOST"),
    port=os.getenv("RABBITMQ_PORT"),
    username=os.getenv("RABBITMQ_USERNAME"),
    password=os.getenv("RABBITMQ_PASSWORD"),
    exchange=os.getenv("RABBITMQ_EXCHANGE"),
    queue_name=os.getenv("RABBITMQ_QUEUE"),
)

with open("database/config.yml", "r") as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)
    PROVIDER_MODELS = CONFIG.get("PROVIDER_MODELS")

LLMBOTMANAGER = {}

ARRAY_BOT_CONFIG = LLMBOT_DATABSE.get_all_bot_config()

LLMBOTMANAGER = load_llm_bot_config(
    provider_models=PROVIDER_MODELS,
    array_bot_config=ARRAY_BOT_CONFIG,
)

logging.info(f"[Init] LLMBOTMANAGER: {LLMBOTMANAGER}")

PIPELINE_TASK = PipelineTask(redis_client=REDIS_CLIENT, rabbit_client=RABBIT_CLIENT)
USER_PROFILE = UserProfile()
TASK_NAMES = ["PRONUNCIATION_CHECKER_TOOL", "GRAMMAR_CHECKER_TOOL"]


class InputRequest(BaseModel):
    user_id: str = None
    bot_id: int = None
    conversation_id: str = None
    message: str = None
    name: str = None
    description: str = None
    task_chain: List[dict] = None
    generation_params: dict = None
    provider_name: str = None
    input_slots: Any = None
    stream: bool = False
    audio_url: str = None
    history: Any = None
    system_prompt: str = None
    format_output: str = None
    

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
ROUTE = "personalized-ai-coach/api"


@app.get(f"/{ROUTE}")
async def health():
    return {"status": "OK"}


@app.get(f"/{ROUTE}/v1/database/listBot")
async def get_list_bot():
    try:
        result = LLMBOT_DATABSE.get_all_bot_config()
        output = []
        if isinstance(result, list):
            for item in result:
                value = {}
                value["id"] = item.get("id")
                value["name"] = item.get("name")
                value["description"] = item.get("description")
                output.append(value)
        return {
            "status": 0,
            "msg": "Success",
            "result": output,
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.post(f"/{ROUTE}/v1/database/insertBot")
async def insert_bot(inputs: InputRequest):
    name = inputs.name
    description = inputs.description
    task_chain = inputs.task_chain
    generation_params = inputs.generation_params
    provider_name = inputs.provider_name
    system_prompt = inputs.system_prompt
    if not isinstance(name, str) or not isinstance(description, str) or not isinstance(task_chain, list) or not isinstance(generation_params, dict) or not isinstance(provider_name, str):
        return {
            "status": -1,
            "msg": "Invalid input",
        }
    if not PROVIDER_MODELS.get(provider_name):
        return {
            "status": -1,
            "msg": f"Provider not found: {provider_name}",
        }
    
    profile_slots = await USER_PROFILE.find_profile_into_scenario(
        data=[task_chain, system_prompt]
    )
    data_inputs = USER_PROFILE.update_data_from_profile(
        data=[task_chain, system_prompt],
        slots=copy.deepcopy(profile_slots),
    )
    task_chain, system_prompt = data_inputs
    
    bot_id = LLMBOT_DATABSE.insert_bot(
        name = name,
        description = description,
        task_chain = task_chain,
        generation_params = generation_params,
        provider_name = provider_name,
        system_prompt = system_prompt,
        format_output = inputs.format_output,
    )
    bot_config = LLMBOT_DATABSE.get_bot_from_id(bot_id)
    if not isinstance(bot_config, dict) or len(bot_config) == 0:
        return {
            "status": -1,
            "msg": "Bot not found",
        }
        
    if LLMBOTMANAGER.get(bot_config.get("provider_name")) is None:
        return {
            "status": -1,
            "msg": "Init LLM fail",
        }
    return {
        "status": 0,
        "msg": "Success",
        "bot_id": bot_id,
    }


@app.post(f"/{ROUTE}/v1/database/updateBot")
async def update_bot(inputs: InputRequest):
    bot_id = inputs.bot_id
    task_chain = inputs.task_chain
    generation_params = inputs.generation_params
    provider_name = inputs.provider_name
    system_prompt = inputs.system_prompt
    if not isinstance(bot_id, int) or not isinstance(task_chain, list) or not isinstance(generation_params, dict) or not isinstance(provider_name, str):
        return {
            "status": -1,
            "msg": "Invalid input",
        }
    if not PROVIDER_MODELS.get(provider_name):
        return {
            "status": -1,
            "msg": f"Provider not found: {provider_name}",
        }
    
    profile_slots = await USER_PROFILE.find_profile_into_scenario(
        data=[task_chain, system_prompt]
    )
    data_inputs = USER_PROFILE.update_data_from_profile(
        data=[task_chain, system_prompt],
        slots=copy.deepcopy(profile_slots),
    )
    task_chain, system_prompt = data_inputs
    
    LLMBOT_DATABSE.update_bot_from_id(
        id = bot_id,
        task_chain = task_chain,
        generation_params = generation_params,
        provider_name = provider_name,
        system_prompt = system_prompt,
        format_output = inputs.format_output,
    )
    bot_config = LLMBOT_DATABSE.get_bot_from_id(bot_id)
    if not isinstance(bot_config, dict) or len(bot_config) == 0:
        return {
            "status": -1,
            "msg": "Bot not found",
        }
    if LLMBOTMANAGER.get(bot_config.get("provider_name")) is None:
        return {
            "status": -1,
            "msg": "Init LLM fail",
        }
    return {
        "status": 0,
        "msg": "Success",
        "bot_id": bot_id,
    }


@app.get(f"/{ROUTE}/v1/database/getDataBot")
async def get_data_bot(bot_id: int):
    try:
        # bot_id = inputs.bot_id
        if not isinstance(bot_id, int):
            return {
                "status": -1,
                "msg": "Bot id must be integer",
            }
        bot_config = LLMBOT_DATABSE.get_bot_from_id(bot_id)
        if not isinstance(bot_config, dict) or len(bot_config) == 0:
            return {
                "status": -1,
                "msg": "Bot not found",
            }
        return {
            "status": 0,
            "msg": "Success",
            "result": bot_config,
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.get(f"/{ROUTE}/v1/database/getHistoryFromConversationId")
async def get_history_from_conversation_id(conversation_id: str):
    try:
        if not isinstance(conversation_id, str):
            return {
                "status": -1,
                "msg": "conversation_id must be string",
            }
        output = LLMBOT_DATABSE.get_output_from_conversation_id(conversation_id)
        if not output:
            return {
                "status": -1,
                "msg": f"conversation_id {conversation_id} is not found",
            }
        return {
            "status": 0,
            "msg": "Success",
            "result": output,
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.post(f"/{ROUTE}/v1/bot/initConversation")
async def init_conversation(inputs: InputRequest):
    bot_id = inputs.bot_id
    input_slots = inputs.input_slots
    conversation_id = inputs.conversation_id
    user_id = inputs.user_id
    try :
        if not isinstance(bot_id, int):
            bot_id = int(bot_id)
    except Exception as e:
        return {
            "status": -1,
            "msg": "Bot id must be integer",
        }
    bot_config = LLMBOT_DATABSE.get_bot_from_id(bot_id)
    if not isinstance(bot_config, dict):
        return {
            "status": 1,
            "msg": "Bot not found",
        }
    if bot_config.get("task_chain") is None:
        return {
            "status": 1,
            "msg": "Task chain not found",
        }
    size_task = len(bot_config.get("task_chain"))
    logging.info(f"[Init Conversation] size_task: {size_task}")
    payload = {
        "conversation_id": conversation_id,
        "input_slots": input_slots,
        "history_task": [[] for _ in range(size_task)],
        "task_idx": 0,
        "pre_task_id": 0,
        "bot_id": bot_id,
        "user_id": user_id,
        "bot_config": bot_config,
        "CUR_STATUS": "INIT",
        "SYSTEM_CONTEXT_VARIABLES": {},
        "TOOL_STATUS": None,
        "TOOL": {
            "TOOL_NAME": None,
            "TOOL_RESULT": None,
            "TOOL_CONVERSATION_ID": None,
            "TOOL_SETTING": None,
        }
    }
    # logging.info(f"[Init Conversation] conversation_id: {conversation_id} - payload: {json.dumps(payload, ensure_ascii=False, indent=4)}")
    logging.info(f"[Init Conversation] conversation_id: {conversation_id}")
    payload = json.dumps(payload, ensure_ascii=False)
    REDIS_CLIENT.set(conversation_id, payload)
    return {
        "status": 0,
        "msg": "Success",
        "conversation_id": conversation_id,
    }


@app.post(f"/{ROUTE}/v1/bot/webhook")
async def webhook(inputs: InputRequest):
    try :
        start_time = time.time()
        conversation_id = inputs.conversation_id
        logging.info(f"[Input] Webhook {conversation_id} : {inputs.json()}")
        output = await process_webhook(inputs)
        conversation = json.loads(REDIS_CLIENT.get(conversation_id))
        if isinstance(output.get("text"), list):
            input_slots_merge = {}
            if isinstance(conversation.get("input_slots"), dict) and len(conversation.get("input_slots")) > 0:
                input_slots_merge.update(
                    copy.deepcopy(conversation.get("input_slots"))
                )
            if isinstance(conversation.get("SYSTEM_CONTEXT_VARIABLES"), dict) and len(conversation.get("SYSTEM_CONTEXT_VARIABLES")) > 0:
                input_slots_merge.update(
                    copy.deepcopy(conversation.get("SYSTEM_CONTEXT_VARIABLES"))
                )
            for idx, text in enumerate(output.get("text")):
                output["text"][idx] = format_text_from_input_slots(
                    text=text,
                    input_slots=input_slots_merge
                )
        
        process_time = time.time() - start_time
        try :
            if isinstance(output, dict):
                output["process_time"] = process_time
                output["SYSTEM_CONTEXT_VARIABLES"] = conversation.get("SYSTEM_CONTEXT_VARIABLES")
                output["task_idx"] = conversation.get("task_idx")
                output["text"] = PIPELINE_TASK.normalize_response_split(
                    text = output.get("text"),
                    variables = conversation.get("SYSTEM_CONTEXT_VARIABLES")
                )
            bot_id = conversation.get("bot_id")
            LLMBOT_DATABSE.insert_llm_history(
                conversation_id = conversation_id,
                input_text = inputs.message,
                output_text = json.dumps(output, ensure_ascii=False),
                process_time= process_time,
                bot_id = bot_id
            )
            if output.get("status") == "END" and output.get("text") in [["ACTION"], "ACTION"]:
                REDIS_CLIENT.delete(conversation_id)
        except Exception as e:
            logging.info(f"[Error] Insert Data {traceback.format_exc()}")
        logging.info(f"[Webhook] {conversation_id} - Process Time: {process_time} - output = {output}")
        return output
    except Exception as e:
        return {
            "status": "END",
            "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
            "conversation_id": conversation_id,
            "msg": f"Bad request {traceback.format_exc()}",
        }


async def process_webhook(inputs: InputRequest):
    try:
        start_time = time.time()
        conversation_id = inputs.conversation_id
        audio_url = inputs.audio_url
        if REDIS_CLIENT.get(conversation_id) is None:
            return {
                "status": "END",
                "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
                "conversation_id": conversation_id,
                "msg": f"Cant find conversation_id: {conversation_id}",
            }
        conversation = json.loads(REDIS_CLIENT.get(conversation_id))
        logging.info(f"[Webhook] {conversation_id}")
        bot_id = conversation.get("bot_id")
        provider_name = conversation.get("bot_config").get("provider_name")
        message = inputs.message
        history_task = conversation.get("history_task")
        task_idx = conversation.get("task_idx")

        logging.info(f"[Webhook] {conversation_id} - TOOL_STATUS: {conversation.get('TOOL_STATUS')} - {conversation.get('TOOL')}")

        if conversation.get("TOOL_STATUS") == "PROCESSING" and isinstance(conversation.get("TOOL"), dict) and isinstance(conversation.get("TOOL").get("TOOL_SETTING"), dict):
            res_webhook_tool = await async_webhook(
                conversation_id=conversation.get("TOOL").get("TOOL_CONVERSATION_ID"),
                robot_type=conversation.get("TOOL").get("TOOL_SETTING").get("robot_type"),
                message=message,
                bot_id=bot_id,
            )
            if isinstance(res_webhook_tool, dict):
                if res_webhook_tool.get("status") == "END":
                    conversation["TOOL_STATUS"] = None
                    conversation["TOOL"] = {}
                    response = conversation["response"]
                    cur_action = response.get("answer")
                    call_status = response.get("status")
                    if not isinstance(cur_action, list):
                        cur_action = [cur_action]
                    cur_action = res_webhook_tool.get("text") + cur_action
                    REDIS_CLIENT.set(conversation_id, json.dumps(conversation, ensure_ascii=False))
                    return {
                        "status": call_status,
                        "text": cur_action if isinstance(cur_action, list) else [cur_action],
                        "conversation_id": conversation_id,
                        "msg": "scuccess",
                        "language": response.get("language"),
                    }
                return res_webhook_tool

        ## ADD TASK CHECK CALL TOOL INTO RABBITMQ
        task_check_call_tools = []
        if isinstance(task_idx, int) and task_idx < len(conversation.get("bot_config").get("task_chain")) and conversation.get("TOOL_STATUS") != "PROCESSING" and conversation.get("CUR_STATUS") not in ["END", "ERROR", "ACTION"]:
            history = history_task[task_idx]
            task = copy.deepcopy(conversation.get("bot_config").get("task_chain")[task_idx])
            for task_name in TASK_NAMES:
                if isinstance(task, dict) and isinstance(task.get(task_name), dict) and len(task.get(task_name)) > 0:
                    task_check_call_tools.append(
                        {
                            "task_name": task_name,
                            "conversation_id": f"{conversation_id}_{task_name}_{str(uuid.uuid4())}",
                            "history": history,
                            "message": message,
                            "task_id": f"{conversation_id}_{task_name}_{str(uuid.uuid4())}",
                            "audio_url": audio_url,
                            "tool": task.get(task_name),
                            "bot_id": bot_id,
                        }
                    )
            if len(task_check_call_tools) > 0:
                task_check_call_tools.append({
                    "task_name": "CHECK_CALL_TOOL",
                    "conversation_id": f"{conversation_id}_CHECK_CALL_TOOL_{str(uuid.uuid4())}",
                    "history": history,
                    "message": message,
                    "task_id": f"{conversation_id}_{task_name}_{str(uuid.uuid4())}",
                    "audio_url": audio_url,
                    "tool": None,
                    "bot_id": bot_id,
                })
            if history and len(task_check_call_tools) > 0:
                task_check_call_tool_id = conversation_id + "_" + str(uuid.uuid4())
                for task_check_call_tool in task_check_call_tools:
                    RABBIT_CLIENT.send_task(
                        message=json.dumps(task_check_call_tool, ensure_ascii=False)
                )
                conversation["TOOL_STATUS"] = "PROCESSING"
        else :
            history = None
            conversation["TOOL_STATUS"] = None
        
        conversation["pre_task_id"] = conversation.get("task_idx")
        conversation["pre_response"] = copy.deepcopy(conversation.get("response"))

        ## Predict With History
        history = inputs.history
        if isinstance(history, list) and len(history) > 0:
            history_format = copy.deepcopy(PIPELINE_TASK.prompt)
            system_prompt = conversation.get("bot_config").get("system_prompt")
            if system_prompt not in ["", None]:
                history_format[0]["content"] = copy.deepcopy(system_prompt)
            task = conversation.get("bot_config").get("task_chain")[conversation.get("task_idx")]
            history_format = format_prompt_from_variable(history_format, task)
            history = history_format + history
        else :
            history = None

        history_task, task_idx, response, system_context_variables, cur_status = await PIPELINE_TASK.process(
            text = message,
            task_idx = conversation.get("task_idx"),
            history_task = history_task,
            task_chain = conversation.get("bot_config").get("task_chain"),
            llm_base = LLMBOTMANAGER.get(provider_name) if LLMBOTMANAGER.get(provider_name) is not None else LLMBOTMANAGER.get("openai"),
            generation_params = conversation.get("bot_config").get("generation_params"),
            conversation_id = conversation_id,
            system_context_variables = conversation.get("SYSTEM_CONTEXT_VARIABLES"),
            history = history,
            system_prompt = conversation.get("bot_config").get("system_prompt"),
            format_output = conversation.get("bot_config").get("format_output"),
            cur_status = conversation.get("CUR_STATUS"),
            bot_id = bot_id,
            input_slots = conversation.get("input_slots"),
            user_id = conversation.get("user_id"),
        )
        conversation["history_task"] = history_task
        conversation["task_idx"] = task_idx
        conversation["response"] = response
        conversation["CUR_STATUS"] = cur_status
        conversation["SYSTEM_CONTEXT_VARIABLES"] = system_context_variables
        logging.info(f"[PROCESS WEBHOOK] SYSTEM_CONTEXT_VARIABLES: {system_context_variables}")

        pre_response = conversation.get("pre_response")
        cur_action = response.get("answer")
        call_status = response.get("status")
        REDIS_CLIENT.set(conversation_id, json.dumps(conversation, ensure_ascii=False))
        if call_status in ["END", "ACTION"]:
            task_chain = conversation.get("bot_config").get("task_chain")
            system_extraction_profile = task_chain[task_idx].get("SYSTEM_EXTRACTION_PROFILE") if isinstance(task_idx, int) and task_idx < len(task_chain) and isinstance(task_chain[task_idx], dict) else None
            history = history_task[task_idx] if isinstance(task_idx, int) and task_idx < len(history_task) else None
            message_profile = USER_PROFILE.get_message_of_profile(
                input_slots=conversation.get("input_slots"),
                system_extraction_profile = system_extraction_profile,
                history=history
            )
            logging.info(f"===============[Webhook] {conversation_id} - task_idx: {task_idx} - message_profile: {message_profile}")
            if message_profile:
                task_id = conversation_id + "_USER_PROFILE"
                REDIS_CLIENT.set(task_id, "PROCESSING", expire_time=30)
                RABBIT_CLIENT.send_task(
                    message=json.dumps(
                        {
                            "task_name": "USER_PROFILE",
                            # "url": str(os.getenv("URL_PROFILE")) + "/updateUserProfile",
                            "messages": message_profile,
                            "conversation_id": conversation_id,
                            "task_id": task_id,
                        },
                        ensure_ascii=False,
                    ) 
                )
        
        ## CHECK RESULT CALL TOOL IN RABBITMQ
        if conversation.get("TOOL_STATUS") == "PROCESSING" and len(task_check_call_tools) > 0:
            while time.time() - start_time < 2.5:
                status_end = True
                for task_check_call_tool in task_check_call_tools:
                    task_id = task_check_call_tool.get("task_id")
                    if REDIS_CLIENT.get(task_id) is None:
                        status_end = False
                        break
                if status_end:
                    break
                await asyncio.sleep(0.1)
            for task_check_call_tool in task_check_call_tools:
                logging.info(f"===============[Webhook] {conversation_id} - task_check_call_tool: {task_check_call_tool.get('task_name')} - {REDIS_CLIENT.get(task_check_call_tool.get('task_id'))}")
            task_check_call_tool_id = task_check_call_tools[-1].get("task_id")
            result_check_call_tool = REDIS_CLIENT.get(task_check_call_tool_id)
            result_check_call_tool = parsing_json(result_check_call_tool)
            if isinstance(result_check_call_tool, dict) and result_check_call_tool.get("status") == 200 and result_check_call_tool.get("result") == True:
                for task_check_call_tool in task_check_call_tools[:-1]:
                    output = REDIS_CLIENT.get(task_check_call_tool.get("task_id"))
                    output = parsing_json(output)
                    if isinstance(output, dict) and output.get("status") == 200 and isinstance(output.get("result"), dict):
                        tool_res = output.get("result").get("TOOL_RESULT")
                        if task_check_call_tool.get("task_name") == "PRONUNCIATION_CHECKER_TOOL":
                            START_MESSAGE = tool_res.get("feedback")
                            TARGET_ANSWER = tool_res.get("target")
                        else :
                            START_MESSAGE = tool_res.get("explanation")
                            TARGET_ANSWER = tool_res.get("fixed_answer")
                        init_status = await async_init_conversation(
                            conversation_id = task_check_call_tool.get("task_id"),
                            robot_type = task_check_call_tool.get("tool").get("robot_type"),
                            robot_type_id = task_check_call_tool.get("tool").get("robot_type_id"),
                            input_slots = {
                                "START_MESSAGE": START_MESSAGE,
                                "TARGET_ANSWER": TARGET_ANSWER,
                            },
                            is_tool = True,
                            user_id = conversation.get("user_id"),
                        )
                        if init_status == True:
                            res_webhook_tool = await async_webhook(
                                conversation_id=task_check_call_tool.get("task_id"),
                                robot_type=task_check_call_tool.get("tool").get("robot_type"),
                                message="alo",
                                first_message="alo",
                                bot_id=bot_id,
                            )
                            if isinstance(res_webhook_tool, dict):
                                conversation["TOOL_STATUS"] = "PROCESSING"
                                conversation["TOOL"] = {
                                    "TOOL_NAME": task_check_call_tool.get("task_name"),
                                    "TOOL_RESULT": output,
                                    "TOOL_CONVERSATION_ID": task_check_call_tool.get("task_id"),
                                    "TOOL_SETTING": task_check_call_tool.get("tool"),
                                }
                                REDIS_CLIENT.set(conversation_id, json.dumps(conversation, ensure_ascii=False))
                                return res_webhook_tool
            conversation["TOOL_STATUS"] = None
        else :
            conversation["TOOL_STATUS"] = None
                
        return {
            "status": call_status,
            "text": cur_action if isinstance(cur_action, list) else [cur_action],
            "conversation_id": conversation_id,
            "msg": "scuccess",
            "language": response.get("language"),
        }
    except Exception as e:
        logging.info(f"[Error] {traceback.format_exc()}")
        return {
            "status": "END",
            "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
            "conversation_id": conversation_id,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.post(f"/{ROUTE}/v1/bot/runExtractAndGeneration")
async def run_extract_and_generation(inputs: InputRequest):
    try :
        start_time = time.time()
        conversation_id = inputs.conversation_id
        if conversation_id is None or REDIS_CLIENT.get(conversation_id) is None:
            return {
                "status": -1,
                "msg": "Conversation ID is not found",
                "conversation_id": conversation_id,
            }
        conversation = json.loads(REDIS_CLIENT.get(conversation_id))
        if conversation.get("CUR_STATUS") not in ["END", "ERROR"]:
            return {
                "status": -1,
                "msg": "Conversation ID is not END",
                "conversation_id": conversation_id,
            }

        task_idx = conversation.get("task_idx")
        provider_name = conversation.get("bot_config").get("provider_name")
        system_context_variables = await PIPELINE_TASK.run_param_extractor(
            task_chain=conversation.get("bot_config").get("task_chain"),
            history=conversation.get("history_task")[task_idx],
            generation_params=conversation.get("bot_config").get("generation_params"),
            llm_base=LLMBOTMANAGER.get(provider_name) if LLMBOTMANAGER.get(provider_name) is not None else LLMBOTMANAGER.get("openai"),
            system_context_variables=conversation.get("SYSTEM_CONTEXT_VARIABLES"),
            task_idx=task_idx,
        )
        process_time = time.time() - start_time
        return {
            "status": 0,
            "msg": "scuccess",
            "record": system_context_variables,
            "process_time": process_time,
        }
    except Exception as e:
        return {
            "status": -1,
            "conversation_id": conversation_id,
            "msg": f"Bad request {traceback.format_exc()}",
        }


if __name__ == "__main__":
    uvicorn.run("app:app", host=args.host, port=args.port, workers=args.workers)
from fastapi import FastAPI, Request
from pydantic import BaseModel
import asyncio
import os, logging
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
import argparse, yaml, copy, time, ssl
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from src.utils.utils import get_provider, load_llm_bot_config, init_llm_bot_config, call_api_get_gifs
from src.channel.mysql_bot import LLMBot
from src.channel.redis_client import RedisClient
from src.tools.tool_config import TOOL_OBJECTS
from src.chatbot.prompt import format_prompt_from_variable
from src.chatbot.lesson_policies import LessonPolicies
from src.chatbot.text_filter import TextFilter


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




PATH_FILE_CONFIG = os.getenv("PATH_FILE_CONFIG") if os.getenv("PATH_FILE_CONFIG") is not None else "config.yml"
with open(PATH_FILE_CONFIG, "r") as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)
    PROVIDER_MODELS = CONFIG.get("PROVIDER_MODELS")

LESSON_POLICIES = LessonPolicies(
    config=CONFIG,
)

TOOL_EXECUTOR_URL = os.getenv("TOOL_EXECUTOR_URL") if os.getenv("TOOL_EXECUTOR_URL") is not None else ""

# Initialize the text filter
TEXT_FILTER = TextFilter()

class InputRequest(BaseModel):
    user_id: str = None
    bot_id: int = None
    name: str = None
    description: str = None
    scenario: Any = None
    # system_prompt: str = None
    # provider_name: str = None
    # generation_params: dict = None

    conversation_id: str = None
    message: str = None
    input_slots: Any = None
    audio_url: Optional[str] = None  
    history: Any = None
    first_message: Optional[str] = None
    start_message: str = None
    

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
ROUTE = "robot-ai-lesson/api"


@app.get(f"/{ROUTE}")
async def health():
    return {"status": "OK"}


@app.get(f"/{ROUTE}/v1/health")
async def health_check():
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
    scenario = inputs.scenario
    if not isinstance(name, str) or not isinstance(description, str):
        return {
            "status": -1,
            "msg": "Invalid input",
        }
        
    ## Update Scenario fill profile:
    if not isinstance(scenario, str):
        scenario = json.dumps(scenario, ensure_ascii=False)
    profile_slots = await LESSON_POLICIES.prompt_processor.find_profile_into_scenario(scenario)
    logging.info(f"[Update Bot]: profile_slots {profile_slots}")
    scenario = LESSON_POLICIES.prompt_processor.update_data_from_profile(scenario, profile_slots)
    scenario = json.loads(scenario)
        
    bot_id = LLMBOT_DATABSE.insert_bot(
        name = name,
        description = description,
        scenario = scenario
    )
    bot_config = LLMBOT_DATABSE.get_bot_from_id(bot_id)
    if not isinstance(bot_config, dict) or len(bot_config) == 0:
        return {
            "status": -1,
            "msg": "Bot not found",
        }
    return {
        "status": 0,
        "msg": "Success",
        "bot_id": bot_id,
    }


@app.post(f"/{ROUTE}/v1/database/updateBot")
async def update_bot(inputs: InputRequest):
    bot_id = inputs.bot_id
    scenario = inputs.scenario
    if not isinstance(bot_id, int) or not isinstance(scenario, list):
        return {
            "status": -1,
            "msg": "Invalid input",
        }
    
    ## Update Scenario fill profile:
    if not isinstance(scenario, str):
        scenario = json.dumps(scenario, ensure_ascii=False)
    profile_slots = await LESSON_POLICIES.prompt_processor.find_profile_into_scenario(scenario)
    logging.info(f"[Update Bot]: profile_slots {profile_slots}")
    scenario = LESSON_POLICIES.prompt_processor.update_data_from_profile(scenario, profile_slots)
    scenario = json.loads(scenario)
    
    status = LLMBOT_DATABSE.update_bot_from_id(
        id = bot_id,
        scenario = scenario,
        name = inputs.name,
        description = inputs.description,
    )
    bot_config = LLMBOT_DATABSE.get_bot_from_id(bot_id)
    if not isinstance(bot_config, dict) or len(bot_config) == 0:
        return {
            "status": -1,
            "msg": "Bot not found",
        }
    if status == False:
        return {
            "status": -1,
            "msg": "Update bot fail",
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
    if not bot_config.get("scenario"):
        return {
            "status": 1,
            "msg": "scenario is not found",
        }
    
    # Clear text filter history for this conversation
    TEXT_FILTER.clear_history(conversation_id)
    
    scenario = bot_config.get("scenario")
    gif_list = []
    if isinstance(scenario, list):
        for component in scenario:
            if isinstance(component, dict) and component.get("robot_type") == "Workflow":
                gifs = await call_api_get_gifs(bot_id=component.get("robot_type_id"))
                if isinstance(gifs, list) and len(gifs) > 0:
                    gif_list.extend(gifs)
    
    payload = {
        "conversation_id": conversation_id,
        "bot_id": bot_id,
        "user_id": inputs.user_id,
        # "scenario": scenario,
        "input_slots": input_slots if isinstance(input_slots, dict) else {},
        "bot_config": bot_config,
        "record": {
            "CUR_TASK_STATUS": "INIT",
            "NEXT_ACTION": -1,
        }
    }
    logging.info(f"[Init Conversation] conversation_id: {conversation_id} - payload: {json.dumps(payload, ensure_ascii=False, indent=4)}")
    # logging.info(f"[Init Conversation] conversation_id: {conversation_id}")
    REDIS_CLIENT.set(conversation_id, json.dumps(payload, ensure_ascii=False))
    return {
        "status": 0,
        "msg": "Success",
        "conversation_id": conversation_id,
        "gifs": gif_list,
    }


@app.post(f"/{ROUTE}/v1/bot/webhook")
async def webhook(inputs: InputRequest):
    try :
        start_time = time.time()
        conversation_id = inputs.conversation_id
        logging.info(f"[Input] Webhook {conversation_id} : {inputs.json()}")
        
        # Apply text filtering
        filtered_text, was_filtered, fixed_response = TEXT_FILTER.filter_text(inputs.message, conversation_id)
        
        # If we have a fixed response for incorrect input, return it directly
        
            
        # If the text was filtered, log it
        if was_filtered:
            logging.info(f"Text filtered for conversation {conversation_id}: '{inputs.message}' -> '{filtered_text}'")
            
        # Get conversation from Redis
        conversation = json.loads(REDIS_CLIENT.get(conversation_id))
        
        # Process with the filtered text
        status, output, record_new, slots_new = await LESSON_POLICIES.process(
            scenario=conversation.get("bot_config").get("scenario"),
            message=filtered_text,  # Use filtered text instead of original
            record=conversation.get("record"),
            input_slots=conversation.get("input_slots"),
            config=CONFIG,
            conversation_id=conversation_id,
            audio_url=inputs.audio_url,
            user_id=conversation.get("user_id"),
        )
        if isinstance(slots_new, dict) and len(slots_new) > 0:
            conversation["input_slots"].update(slots_new)
        if record_new.get("RULE"):
            nex_action = record_new.get("NEXT_ACTION")
            conversation["bot_config"]["scenario"][nex_action]["robot_type"] = record_new.get("RULE").get("robot_type")
            conversation["bot_config"]["scenario"][nex_action]["robot_type_id"] = record_new.get("RULE").get("robot_type_id")
            del record_new["RULE"]

            logging.info(f"===================conversation['bot_config']['scenario'][nex_action]: {conversation['bot_config']['scenario'][nex_action]}")

        conversation["record"] = record_new
        conversation["logs"] = copy.deepcopy(output)
        nex_action = record_new.get("NEXT_ACTION")
        scenario=conversation.get("bot_config").get("scenario")
        robot_type = None
        if isinstance(nex_action, int) and isinstance(scenario, list) and nex_action < len(scenario) and isinstance(scenario[nex_action], dict):
            robot_type = scenario[nex_action].get("robot_type")
        res = {}
        process_time = time.time() - start_time
        if status == "ERROR":
            return LESSON_POLICIES.get_message_error(conversation_id=conversation_id, message_error=str(traceback.format_exc()))
            # res = {
            #     "status": "END",
            #     "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
            #     "conversation_id": conversation_id,
            #     "record": record_new,
            #     "logs": conversation.get("logs"),
            #     "mood": "",
            #     "image": "",
            #     "video": "",
            #     "volume": None,
            #     "robot_type": robot_type,
            # }
        else :
            logging.info(f"==========================output: {output}")
            res["status"] = status
            res["text"] = output.get("text")
            res["record"] = record_new
            res["conversation_id"] = conversation.get("conversation_id")
            res["input_slots"] = conversation.get("input_slots")
            res["logs"] = conversation.get("logs")
            res["robot_type"] = robot_type
            logs = conversation.get("logs")
            logs_record = None
            if isinstance(logs, dict):
                logs_record = copy.deepcopy(logs.get("record"))
                if isinstance(logs.get("SYSTEM_CONTEXT_VARIABLES"), dict) and logs.get("SYSTEM_CONTEXT_VARIABLES") and not logs_record:
                    logs_record = copy.deepcopy(logs.get("SYSTEM_CONTEXT_VARIABLES"))
            if isinstance(logs_record, dict):
                # res["mood"] = logs_record.get("MOOD") if logs_record.get("MOOD") is not None else ""
                # res["image"] = logs_record.get("IMAGE") if logs_record.get("IMAGE") is not None else ""
                # res["video"] = logs_record.get("VIDEO") if logs_record.get("VIDEO") is not None else ""
                # res["moods"] = logs_record.get("MOODS") if logs_record.get("MOODS") else None
                # res["voice_speed"] = logs_record.get("VOICE_SPEED") if logs_record.get("VOICE_SPEED") else None
                # res["text_viewer"] = logs_record.get("TEXT_VIEWER") if logs_record.get("TEXT_VIEWER") else ""
                # res["volume"] = logs_record.get("VOLUME") if logs_record.get("VOLUME") else None
                res["audio_listening"] = logs_record.get("AUDIO_LISTENING") if logs_record.get("AUDIO_LISTENING") else None
                res["image_listening"] = logs_record.get("IMAGE_LISTENING") if logs_record.get("IMAGE_LISTENING") else None
                res["listening_animations"] = logs_record.get("LISTENING_ANIMATIONS") if logs_record.get("LISTENING_ANIMATIONS") else None
                res["language"] = logs_record.get("LANGUAGE") if logs_record.get("LANGUAGE") else None
                res["answer_mode"] = logs_record.get("ANSWER_MODE") if logs_record.get("ANSWER_MODE") else None
                res["trigger"] = logs_record.get("TRIGGER") if logs_record.get("TRIGGER") else None
                res["tool_recording"] = logs_record.get("TOOL_RECORDING") if logs_record.get("TOOL_RECORDING") else None
                res["tool_score"] = logs_record.get("TOOL_SCORE") if logs_record.get("TOOL_SCORE") else None

                if status == "ACTION" and record_new.get("CUR_TASK_STATUS") in ["END", "ERROR"]:
                    scenario, next_action = LESSON_POLICIES.update_task(
                        scenario=conversation.get("bot_config").get("scenario"),
                        next_action=record_new.get("NEXT_ACTION"),
                        trigger=logs_record.get("TRIGGER"),
                    )
                    logging.info(f"==============[Update Task] scenario: {scenario} - next_action: {next_action}")
                    if next_action >= len(scenario):
                        record_new["CUR_TASK_STATUS"] = "END"
                        res["status"] = "END"
                    record_new["NEXT_ACTION"] = next_action
                    conversation["bot_config"]["scenario"] = scenario
                    conversation["record"] = record_new
            else :
                # res["mood"] = ""
                # res["image"] = ""
                # res["video"] = ""
                # res["moods"] = None
                # res["listening_animations"] = None
                # res["language"] = None
                # res["voice_speed"] = None
                # res["text_viewer"] = ""
                # res["volume"] = None
                res["audio_listening"] = None
                res["image_listening"] = None
                res["listening_animations"] = None
                res["language"] = None
                res["trigger"] = None
                res["answer_mode"] = "RECORDING"
                res["tool_recording"] = None
                res["tool_score"] = None
        try :
            bot_id = conversation.get("bot_id")
            LLMBOT_DATABSE.insert_llm_history(
                conversation_id = conversation_id,
                input_text = inputs.message,
                output_text = json.dumps(res, ensure_ascii=False),
                process_time= process_time,
                bot_id = bot_id
            )

            logging.info(f"[Webhook] {conversation_id} - Process Time: {process_time} - output = {res}")
            if isinstance(res, dict):
                res["process_time"] = process_time
            if res.get("status") == "END":
                REDIS_CLIENT.delete(conversation_id)
            else :
                REDIS_CLIENT.set(conversation_id, json.dumps(conversation, ensure_ascii=False))
            if fixed_response:
                res.update({
                    "text": [fixed_response]
                })
                
        except Exception as e:
            logging.info(f"[Error] webhook {traceback.format_exc()}")
        logging.info(f"[Webhook] {conversation_id} - Process Time: {process_time} - output = {res}")
        return res
    except Exception as e:
        logging.info(f"[Error] webhook {traceback.format_exc()}")
        return LESSON_POLICIES.get_message_error(conversation_id=conversation_id, message_error=str(traceback.format_exc()))
        # return res
        #     "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
        #     "conversation_id": conversation_id,
        #     "msg": f"Bad request {traceback.format_exc()}",
        #     "mood": "",
        #     "image": "",
        #     "video": "",
        #     "robot_type": None,
        # }


@app.post(f"/{ROUTE}/v1/bot/extractFacts")
async def extract_facts(inputs: InputRequest):
    try:
        conversation_id = inputs.conversation_id
        user_id = inputs.user_id
        if not isinstance(conversation_id, str):
            return {
                "status": -1,
                "msg": "conversation_id must be string",
            }
        history = LLMBOT_DATABSE.get_output_from_conversation_id(conversation_id)
        conversation = []
        for content in history:
            conversation.append({
                "role": "user",
                "content": content.get("user"),
            })
            conversation.append({
                "role": "assistant",
                "content": content.get("assistant"),
            })

        if not conversation:
            return {
                "status": -1,
                "msg": f"conversation_id {conversation_id} is not found",
            }
        output = await LESSON_POLICIES.async_call_api(
            url = f"{TOOL_EXECUTOR_URL}/extractFacts",
            method = "POST",
            headers = {
                "Content-Type": "application/json"
            },
            payload = {
                "metadata": {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "conversation": conversation,
                }
            }
        )

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
    
    
@app.post(f"/{ROUTE}/v1/bot/summaryConversation")
async def summary_conversation(inputs: InputRequest):
    try:
        conversation_id = inputs.conversation_id
        if not isinstance(conversation_id, str):
            return {
                "status": -1,
                "msg": "conversation_id must be string",
            }
        history = LLMBOT_DATABSE.get_output_from_conversation_id(conversation_id)
        conversation = []
        for content in history:
            conversation.append({
                "role": "user",
                "content": content.get("user"),
            })
            conversation.append({
                "role": "assistant",
                "content": content.get("assistant"),
            })

        if not conversation:
            return {
                "status": -1,
                "msg": f"conversation_id {conversation_id} is not found",
            }
        
        output = await LESSON_POLICIES.async_call_api(
            url = f"{TOOL_EXECUTOR_URL}/summaryConversation",
            method = "POST",
            headers = {
                "Content-Type": "application/json"
            },
            payload = {
                "conversation_id": conversation_id,
                "messages": conversation,
            }
        )

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


def format_text_from_input_slots(input_slots: dict, text: str):
    if not isinstance(input_slots, dict) or not isinstance(text, str):
        return text
    text = re.sub(r'\s+', ' ', text)
    for key, value in input_slots.items():
        if text.find("{{" + key + "}}") != -1:
            text = text.replace("{{" + key + "}}", str(value))
    return text


if __name__ == "__main__":
    uvicorn.run("app:app", host=args.host, port=args.port, workers=args.workers)
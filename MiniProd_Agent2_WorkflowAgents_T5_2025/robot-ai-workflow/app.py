from fastapi import FastAPI, Request, Form
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
import argparse, yaml, copy, time
from datetime import datetime
from fastapi.responses import StreamingResponse
from src.utils.utils import get_provider, load_llm_bot_config, init_llm_bot_config, call_api_get_user_profile, hash_string_sha256
from src.channel.mysql_bot import LLMBot
from src.channel.redis_client import RedisClient
from src.chatbot.pipeline_task import PipelineTask
from src.tools.tool_config import TOOL_OBJECTS
from src.chatbot.prompt import format_prompt_from_variable
from src.chatbot.scenario import ScenarioExcel
from src.chatbot.policies import PoliciesWorkflow
from fastapi.middleware.cors import CORSMiddleware


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

SCENARIO_EXCEL = ScenarioExcel()
POLICIES_WORKFLOW = PoliciesWorkflow()

PATH_FILE_CONFIG = os.getenv("PATH_FILE_CONFIG") if os.getenv("PATH_FILE_CONFIG") is not None else "config.yml"
with open(PATH_FILE_CONFIG, "r") as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)
    PROVIDER_MODELS = CONFIG.get("PROVIDER_MODELS")

LLMBOTMANAGER = {}

ARRAY_BOT_CONFIG = LLMBOT_DATABSE.get_all_bot_config()

LLMBOTMANAGER = load_llm_bot_config(
    provider_models=PROVIDER_MODELS,
    array_bot_config=ARRAY_BOT_CONFIG,
)

logging.info(f"[Init] LLMBOTMANAGER: {LLMBOTMANAGER}")

PIPELINE_TASK = PipelineTask()


class InputRequest(BaseModel):
    user_id: str = None
    bot_id: int = None
    name: str = None
    description: str = None
    scenario: Any = None
    system_prompt: str = None
    system_extraction_variables: str = None
    system_prompt_generation: str = None
    provider_name: str = None
    generation_params: dict = None
    system_extraction_profile: str = None

    conversation_id: str = None
    message: str = None
    input_slots: Any = None
    audio_url: Optional[str] = None  
    history: Any = None
    question_idx: int = None
    data_excel: Any = None
    first_message: Optional[str] = None
    start_message: Any = None
    is_tool: bool = False
    

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
ROUTE = "robot-ai-workflow/api"


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
    generation_params = inputs.generation_params
    provider_name = inputs.provider_name
    data_excel = inputs.data_excel
    start_message = inputs.start_message
    if not isinstance(name, str) or not isinstance(description, str) or not isinstance(data_excel, list) or not isinstance(generation_params, dict) or not isinstance(provider_name, str):
        return {
            "status": -1,
            "msg": "Invalid input",
        }
    if not PROVIDER_MODELS.get(provider_name):
        return {
            "status": -1,
            "msg": f"Provider not found: {provider_name}",
        }
    
    ## Set input_slots for scenario
    profile_slots = await SCENARIO_EXCEL.find_profile_into_scenario(
        data=[inputs.system_prompt, inputs.system_extraction_variables, inputs.system_prompt_generation, inputs.system_extraction_profile, start_message]
    )
    data_inputs = SCENARIO_EXCEL.update_data_from_profile(
        data=[inputs.system_prompt, inputs.system_extraction_variables, inputs.system_prompt_generation, inputs.system_extraction_profile, start_message],
        slots=copy.deepcopy(profile_slots),
    )
    system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, start_message = data_inputs


    profile_slots = await SCENARIO_EXCEL.find_profile_into_scenario(data=data_excel)
    data_excel_norm = SCENARIO_EXCEL.update_data_from_profile(
        data=data_excel,
        slots=profile_slots,
    )
    scenario = SCENARIO_EXCEL.convert_data_excel_to_scenario(
        start_message=start_message,
        data=data_excel_norm
    )
    bot_id = LLMBOT_DATABSE.insert_bot(
        name = name,
        description = description,
        scenario = scenario,
        system_prompt = system_prompt,
        generation_params = generation_params,
        provider_name = provider_name,
        system_extraction_variables = system_extraction_variables,
        system_prompt_generation = system_prompt_generation,
        system_extraction_profile = system_extraction_profile,
        data_excel = data_excel,
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
    data_excel = inputs.data_excel
    generation_params = inputs.generation_params
    provider_name = inputs.provider_name
    start_message = inputs.start_message
    if not isinstance(bot_id, int) or not isinstance(data_excel, list) or not isinstance(generation_params, dict) or not isinstance(provider_name, str):
        return {
            "status": -1,
            "msg": "Invalid input",
        }
    if not PROVIDER_MODELS.get(provider_name):
        return {
            "status": -1,
            "msg": f"Provider not found: {provider_name}",
        }
    
    ## Set input_slots for scenario
    profile_slots = await SCENARIO_EXCEL.find_profile_into_scenario(
        data=[inputs.system_prompt, inputs.system_extraction_variables, inputs.system_prompt_generation, inputs.system_extraction_profile, start_message]
    )
    data_inputs = SCENARIO_EXCEL.update_data_from_profile(
        data=[inputs.system_prompt, inputs.system_extraction_variables, inputs.system_prompt_generation, inputs.system_extraction_profile, start_message],
        slots=copy.deepcopy(profile_slots),
    )
    system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, start_message = data_inputs
    
    profile_slots = await SCENARIO_EXCEL.find_profile_into_scenario(data=data_excel)
    data_excel_norm = SCENARIO_EXCEL.update_data_from_profile(
        data=data_excel,
        slots=copy.deepcopy(profile_slots),
    )
    scenario = SCENARIO_EXCEL.convert_data_excel_to_scenario(
        start_message=start_message,
        data=data_excel_norm
    )

    status = LLMBOT_DATABSE.update_bot_from_id(
        id = bot_id,
        name = inputs.name,
        description = inputs.description,
        scenario = scenario,
        generation_params = generation_params,
        provider_name = provider_name,
        system_prompt = system_prompt,
        system_extraction_variables = system_extraction_variables,
        system_prompt_generation = system_prompt_generation,
        system_extraction_profile = system_extraction_profile,
        data_excel = data_excel,
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
        if "scenario" in bot_config.keys():
            bot_config["data_excel"] = SCENARIO_EXCEL.norm_data_excel_with_intent_name_and_description(data=bot_config["data_excel"])
            del bot_config["scenario"]
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


@app.get(f"/{ROUTE}/v1/database/getGifs")
async def get_gifs(bot_id: int):
    try:
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
        scenario = bot_config.get("scenario")
        gif_list = SCENARIO_EXCEL.get_gifs_from_scenario(scenario=scenario)
        return {
            "status": 0,
            "msg": "Success",
            # "result": bot_config,
            "gifs": gif_list,
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
    if not bot_config.get("scenario"):
        return {
            "status": 1,
            "msg": "scenario is not found",
        }
    
    scenario = bot_config.get("scenario")
    scenario_new = SCENARIO_EXCEL.preprocess_scenario(
        scenario=scenario,
        input_slots=input_slots
    )

    # Start Check Extract And Update User Profile
    start_time = time.time()
    while time.time() - start_time < 5:
        if REDIS_CLIENT.get(f"{conversation_id}_USER_PROFILE") in ["END", None]:
            break
        await asyncio.sleep(0.1)
    ## END Check Extract And Update User Profile

    profile_slots = await call_api_get_user_profile(conversation_id=conversation_id)
    if isinstance(profile_slots, dict) and len(profile_slots) > 0:
        if not isinstance(input_slots, dict):
            input_slots = {}
        input_slots.update(profile_slots)

    # if inputs.is_tool == False:
    #     bot_answers = POLICIES_WORKFLOW.get_answer_next_predict(
    #         scenario=scenario_new,
    #         idx=0
    #     )
    #     text_id = hash_string_sha256(bot_answers[0]) if isinstance(bot_answers, list) and len(bot_answers) > 0 else ""
    #     task_id = f"{bot_id}_{conversation_id}_{text_id}"
    #     if user_id is not None:
    #         POLICIES_WORKFLOW.rabbitmq_client.send_task(
    #             message=json.dumps(
    #                 {
    #                     "task_name": "PIKA_MEMORY",
    #                     "conversation_id": conversation_id,
    #                     "task_id": task_id,
    #                     "user_id": user_id,
    #                     "bot_id": bot_id,
    #                     "history": [
    #                         {
    #                             "role": "assistant",
    #                             "content": POLICIES_WORKFLOW.scenario_flow.format_text_from_input_slots(
    #                                 input_slots=input_slots,
    #                                 text=bot_answers[0]
    #                             )
    #                         }
    #                     ]
    #                 },
    #                 ensure_ascii=False,
    #             )
    #         )
    #         REDIS_CLIENT.set(task_id, "PROCESSING", expire_time=5 * 60)
    #     start_time = time.time()
    #     while time.time() - start_time < 5:
    #         if REDIS_CLIENT.get(task_id) != "PROCESSING":
    #             break
    #         await asyncio.sleep(0.2)

    tool_recording = SCENARIO_EXCEL.get_tool_recording_from_scenario(scenario=scenario) if inputs.is_tool != True else None
    logging.info(f"================[Init Conversation] conversation_id: {conversation_id} - inputs.is_tool: {inputs.is_tool} - tool_recording: {tool_recording}")
    bot_config["scenario"] = copy.deepcopy(scenario_new)
    payload = {
        "conversation_id": conversation_id,
        "bot_id": bot_id,
        "user_id": user_id,
        "input_slots": input_slots,
        "bot_config": bot_config,
        "is_tool": inputs.is_tool,
        "record": {
            "status": None,
            "CUR_INTENT": None,
            "INTENT_PREDICT_LLM": None,
            "NEXT_ACTION": 0,
            "PRE_ACTION": None,
            "CUR_ACTION": None,
            "LOOP_COUNT": [{} for i in range(len(scenario))],
            "SYSTEM_SCORE_SUM": 0,
            "HISTORY_QUESTION": [],
            "LANGUAGE": None,
            "MOOD": None,
            "IMAGE": None,
            "VIDEO": None,
            "MOODS": None,
            "LISTENING_ANIMATIONS": None,
            "TOOL_SCORE": {},
            "TOOL": {
                "TOOL_NAME": None,
                "TOOL_PARAM": None,
                "TOOL_RESULT": None,
                "TOOL_CONVERSATION_ID": None,
                "TOOL_RESPONSE": None,
            },
            "ANSWER_MODE": "RECORDING",
            "TOOL_RECORDING": tool_recording
        },
        "history": []
    }
    # logging.info(f"[Init Conversation] conversation_id: {conversation_id} - payload: {json.dumps(payload, ensure_ascii=False, indent=4)}")
    logging.info(f"[Init Conversation] conversation_id: {conversation_id} - {profile_slots}")
    REDIS_CLIENT.set(conversation_id, json.dumps(payload, ensure_ascii=False))
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
        process_time = time.time() - start_time
        # profile_slots = await call_api_get_user_profile(conversation_id=conversation_id)
        # logging.info(f"==================profile_slots[webhook]: {profile_slots}")
        try :
            conversation = json.loads(REDIS_CLIENT.get(conversation_id))
            bot_id = conversation.get("bot_id")
            LLMBOT_DATABSE.insert_llm_history(
                conversation_id = conversation_id,
                input_text = inputs.message,
                output_text = json.dumps(output, ensure_ascii=False),
                process_time= process_time,
                bot_id = bot_id
            )
            if isinstance(output, dict):
                output["process_time"] = process_time
                # output["SYSTEM_CONTEXT_VARIABLES"] = conversation.get("SYSTEM_CONTEXT_VARIABLES")
                # output["task_idx"] = conversation.get("task_idx")
            # if output.get("status") == "END":
            #     REDIS_CLIENT.delete(conversation_id)
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
        conversation_id = inputs.conversation_id
        audio_url = inputs.audio_url
        # audio_url = "https://sufile.stepup.edu.vn/storage/robot/audio/user/250528/888b9ddb-2292-e563-c566-857fa41c5cdb_1748442329102.wav"

        if REDIS_CLIENT.get(conversation_id) is None:
            return {
                "status": "END",
                "text": ["Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"],
                "conversation_id": conversation_id,
                "msg": f"Cant find conversation_id: {conversation_id}",
            }
        conversation = json.loads(REDIS_CLIENT.get(conversation_id))
        provider_name = conversation.get("bot_config").get("provider_name")
        status, answer, record_new = await POLICIES_WORKFLOW.process(
            scenario=conversation.get("bot_config").get("scenario"),
            message=inputs.message,
            record=conversation.get("record"),
            input_slots=conversation.get("input_slots"),
            llm_base=LLMBOTMANAGER.get(provider_name) if LLMBOTMANAGER.get(provider_name) is not None else LLMBOTMANAGER.get("openai"),
            params=conversation.get("bot_config").get("generation_params"),
            conversation_id = conversation_id,
            system_prompt=conversation.get("bot_config").get("system_prompt"),
            history=inputs.history,
            question_idx=inputs.question_idx,
            is_tool=conversation.get("is_tool"),
            audio_url=audio_url,
            bot_id=conversation.get("bot_id"),
            user_id=conversation.get("user_id"),
        )
        record_new["ANSWER_MODE"] = SCENARIO_EXCEL.get_answer_mode_from_scenario(scenario=conversation.get("bot_config").get("scenario"), idx=record_new.get("NEXT_ACTION"))
        if record_new.get("ANSWER_MODE_TOOL") is not None:
            record_new["ANSWER_MODE"] = record_new.get("ANSWER_MODE_TOOL")
        record_new = POLICIES_WORKFLOW.caculate_tool_recording(record_new=record_new)
        conversation["record"] = copy.deepcopy(record_new)
        if isinstance(conversation.get("history"), list):
            if len(conversation.get("history")) == 0:
                conversation["history"].append({
                    "role": "assistant",
                    "content": answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
                })
            else :
                conversation["history"].append({
                    "role": "user",
                    "content": inputs.message if inputs.message else " "
                })
                conversation["history"].append({
                    "role": "assistant",
                    "content": answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
                })
        
        if status == "END":
            system_extraction_profile = conversation.get("bot_config").get("system_extraction_profile")
            message_profile = POLICIES_WORKFLOW.get_message_of_profile(
                input_slots=conversation.get("input_slots"),
                system_extraction_profile = system_extraction_profile,
                history=conversation.get("history")
            )
            if message_profile:
                task_id = conversation_id + "_USER_PROFILE"
                REDIS_CLIENT.set(task_id, "PROCESSING", expire_time=30)
                POLICIES_WORKFLOW.rabbitmq_client.send_task(
                    message=json.dumps(
                        {
                            "task_name": "USER_PROFILE",
                            "url": str(os.getenv("URL_PROFILE")) + "/updateUserProfile",
                            "messages": message_profile,
                            "conversation_id": conversation_id,
                            "task_id": task_id,
                        },
                        ensure_ascii=False,
                    ) 
                )

        REDIS_CLIENT.set(conversation_id, json.dumps(conversation, ensure_ascii=False))
        return {
            "status": status,
            "text": answer if isinstance(answer, list) else [answer],
            "conversation_id": conversation_id,
            "msg": "scuccess",
            "record": record_new,
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
        record_new = copy.deepcopy(conversation.get("record"))
        if not isinstance(record_new, dict) or record_new.get("NEXT_ACTION") not in ["END", "ERROR"]:
            return {
                "status": -1,
                "msg": "Conversation ID is not END",
                "conversation_id": conversation_id,
            }
        provider_name = conversation.get("bot_config").get("provider_name")
        system_context_variables = await POLICIES_WORKFLOW.run_extract_and_generation(
            params=conversation.get("bot_config").get("generation_params"),
            input_slots=conversation.get("input_slots"),
            system_extraction_variables=conversation.get("bot_config").get("system_extraction_variables"),
            system_prompt_generation=conversation.get("bot_config").get("system_prompt_generation"),
            history=conversation.get("history"),
            llm_base=LLMBOTMANAGER.get(provider_name) if LLMBOTMANAGER.get(provider_name) is not None else LLMBOTMANAGER.get("openai")
        )
        if isinstance(system_context_variables, dict) and len(system_context_variables) > 0:
            record_new.update(system_context_variables)
        process_time = time.time() - start_time
        return {
            "status": 0,
            "msg": "scuccess",
            "record": record_new,
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
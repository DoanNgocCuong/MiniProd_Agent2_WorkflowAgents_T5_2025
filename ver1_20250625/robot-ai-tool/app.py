from fastapi import FastAPI, Request
from pydantic import BaseModel
import asyncio
import os, logging, aiohttp
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
import uuid
from fastapi.responses import StreamingResponse
from src.tool_executor import ToolExecutor
from src.channel.redis_client import RedisClient
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

args = parser.parse_args()

PATH_FILE_CONFIG = os.getenv("PATH_FILE_CONFIG") if os.getenv("PATH_FILE_CONFIG") is not None else "config.yml"
with open(PATH_FILE_CONFIG, "r") as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)
    PROVIDER_MODELS = CONFIG.get("PROVIDER_MODELS")
    TOOL_CONFIG = CONFIG.get("TOOL_CONFIG")

URL_PIKA_MEMORY = os.getenv("URL_PIKA_MEMORY") if os.getenv("URL_PIKA_MEMORY") is not None else ""

tool_executor = ToolExecutor(PROVIDER_MODELS, TOOL_CONFIG)

class InputRequest(BaseModel):
    conversation_id: str = None
    tool_name: str = None
    audio_url: Optional[str] = None  
    message: str = None
    text_refs: str = None
    question: str = None
    profile_description: dict = None
    messages: List[dict] = None
    input_slots: dict = None
    bot_type: str = None
    bot_id: int = None
    metadata: dict = None
    

app = FastAPI()
ROUTE = "robot-ai-tool/api"
REDIS_CLIENT = RedisClient(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    password=os.getenv("REDIS_PASSWORD"),
)
RABBITMQ_CLIENT = RabbitMQClient(
    host=os.getenv("RABBITMQ_HOST"),
    port=int(os.getenv("RABBITMQ_PORT")),
    username=os.getenv("RABBITMQ_USERNAME"),
    password=os.getenv("RABBITMQ_PASSWORD"),
    exchange=os.getenv("RABBITMQ_EXCHANGE"),
    queue_name=os.getenv("RABBITMQ_QUEUE"),
)


@app.get(f"/{ROUTE}")
async def health():
    return {"status": "OK"}


@app.post(f"/{ROUTE}/v1/tool/execute")
async def tool_execution(inputs: InputRequest):
    try :
        conversation_id = inputs.conversation_id
        tool_name = inputs.tool_name
        logging.info(f"[START TOOL] {conversation_id} - {tool_name} - {inputs.json()}")
        output = await tool_executor.execute(
            conversation_id=inputs.conversation_id,
            tool_name=inputs.tool_name,
            audio_url=inputs.audio_url,
            message=inputs.message,
            text_refs=inputs.text_refs,
            question=inputs.question,
            metadata=inputs.metadata
        )
        logging.info(f"[END TOOL] {conversation_id} - {output}")
        if not isinstance(output, dict):
            return {
                "status": -1,
                "msg": "Bad request"
            }
        if output.get("msg") is not None:
            return {
                "status": -1,
                "msg": output.get("msg")
            }
        if isinstance(output, dict) and len(output) == 0:
            return {
                "status": 0,
                "result": None,
                "msg": "Success"
            }
        return {
            "status": 0,
            "result": output,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }
    
@app.post(f"/{ROUTE}/v1/tool/profileMatching")
async def profile_matching(inputs: InputRequest):
    try :
        conversation_id = inputs.conversation_id
        logging.info(f"[START TOOL] {conversation_id} - profileMatching")
        output = await tool_executor.profile_matching.process(
            message=inputs.message,
            profile_description=inputs.profile_description,
        )
        logging.info(f"[END TOOL] profileMatching {conversation_id} - {output}")
        if output is None:
            return {
                "status": 0,
                "result": None,
                "msg": "Success"
            }
        return {
            "status": 0,
            "result": output,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }

@app.post(f"/{ROUTE}/v1/tool/profileExtraction")
async def profile_extraction(inputs: InputRequest):
    try :
        conversation_id = inputs.conversation_id
        logging.info(f"[START TOOL] {conversation_id} - profileExtraction")
        output = await tool_executor.profile_extractor.process(
            messages=inputs.messages,
        )
        logging.info(f"[END TOOL] profileExtraction {conversation_id} - {output}")
        if not isinstance(output, dict):
            return {
                "status": 0,
                "result": None,
                "msg": "Success"
            }
        return {
            "status": 0,
            "result": output,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }
    

@app.post(f"/{ROUTE}/v1/tool/makeConversationTemplate")
async def make_conversation_template(inputs: InputRequest):
    try :
        conversation_id = inputs.conversation_id
        input_slots = inputs.input_slots if isinstance(inputs.input_slots, dict) else {}
        bot_type = inputs.bot_type
        bot_id = inputs.bot_id
        if bot_type not in ["Agent", "Workflow", "Lesson"]:
            return {
                "status": -1,
                "conversation_id": conversation_id,
                "msg": "Robot type is required and must be in ['Agent', 'Workflow', 'Lesson']"
            }
        RABBITMQ_CLIENT.send_task(
            message=json.dumps({
                "conversation_id": conversation_id,
                "input_slots": input_slots,
                "bot_type": bot_type,
                "bot_id": bot_id,
            }, ensure_ascii=False)
        )
        REDIS_CLIENT.set(
            key=conversation_id,
            value="INIT",
        )
        return {
            "status": 0,
            "conversation_id": conversation_id,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.get(f"/{ROUTE}/v1/tool/getConversationTemplate")
async def get_conversation_template(conversation_id: str, robot_type: str):
    try :
        if not isinstance(conversation_id, str) or not isinstance(robot_type, str):
            return {
                "status": -1,
                "msg": "conversation_id must be string, robot_type must be string",
                "conversation_status": "NOT_FOUND",
            }
        conversation_status = REDIS_CLIENT.get(conversation_id)
        if conversation_status is None:
            output = await tool_executor.get_conversation_template(conversation_id, robot_type)
            if not output or not isinstance(output, list):
                return {
                    "status": -1,
                    "msg": "Conversation template not found",
                    "conversation_status": "NOT_FOUND",
                }
            return {
                "status": 0,
                "msg": "Success",
                "conversation_status": "END",
                "conversation_id": conversation_id,
                "result": output,
            }
        if conversation_status == "END":
            output = await tool_executor.get_conversation_template(conversation_id, robot_type)
            if not output or not isinstance(output, list):
                return {
                    "status": -1,
                    "msg": "Conversation template not found",
                    "conversation_status": conversation_status,
                }
            return {
                "status": 0,
                "msg": "Success",
                "conversation_status": "END",
                "conversation_id": conversation_id,
                "result": output,
            }
        return {
            "status": -1,
            "conversation_status": conversation_status,
            "conversation_id": conversation_id,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
            "conversation_status": "ERROR",
        }


@app.post(f"/{ROUTE}/v1/tool/properityMatching")
async def properity_matching(inputs: InputRequest):
    try :
        bot_id = inputs.bot_id
        messages = inputs.messages
        conversation_id = inputs.conversation_id
        if not isinstance(messages, list) or not isinstance(bot_id, int):
            return {
                "status": -1,
                "msg": "messages must be list",
            }
        logging.info(f"[START TOOL] {conversation_id} - properityMatching")
        task_list = [
            {
                "task_id": str(uuid.uuid4()),
                "value": "image",
                "task_name": "PROPERITY_MATCHING",
                "job_name": "IMAGE_MATCHING",
            },
            {
                "task_id": str(uuid.uuid4()),
                "value": "language",
                "task_name": "PROPERITY_MATCHING",
                "job_name": "LANGUAGE_MATCHING",
            },
            {
                "task_id": str(uuid.uuid4()),
                "value": "mood",
                "task_name": "PROPERITY_MATCHING",
                "job_name": "MOOD_MATCHING",
            }
        ]

        for task in task_list:
            RABBITMQ_CLIENT.send_task(
                message=json.dumps({
                "conversation_id": conversation_id,
                "bot_id": inputs.bot_id,
                "messages": messages,
                "task_id": task.get("task_id"),
                "task_name": task.get("task_name"),
                "job_name": task.get("job_name"),
            }, ensure_ascii=False)
        )
        start_time = time.time()
        while time.time() - start_time < 5:
            status = True
            for task in task_list:
                if REDIS_CLIENT.get(task.get("task_id")) is None:
                    status = False
                    break
            if status == True:
                break
            await asyncio.sleep(0.1)
        
        result = {}
        for task in task_list:
            value = REDIS_CLIENT.get(task.get("task_id"))
            if not value or value == "NOT_FOUND":
                result[task.get("value")] = None
            else:
                result[task.get("value")] = value
        logging.info(f"[END TOOL] {conversation_id} - properityMatching - {result}")
        return {
            "status": 0,
            "result": result if result else None,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }
    

@app.post(f"/{ROUTE}/v1/tool/checkCallTool")
async def check_call_tool(inputs: InputRequest):
    try:
        conversation_id = inputs.conversation_id
        messages = inputs.messages
        logging.info(f"[START TOOL] {conversation_id} - checkCallTool")
        
        if not isinstance(messages, list):
            return {
                "status": -1,
                "msg": "messages must be list",
            }
            
        output = await tool_executor.check_call_tool.process(
            conversation_history=messages
        )
        
        logging.info(f"[END TOOL] checkCallTool {conversation_id} - {output}")
        return {
            "status": 0,
            "result": output,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.post(f"/{ROUTE}/v1/tool/mem0Generation")
async def mem0_generation(inputs: InputRequest):
    try:
        # conversation_id = inputs.conversation_id
        # logging.info(f"[START TOOL] {conversation_id} - mem0Search")
        # facts_values = []
        # metadata = inputs.metadata
        # if not isinstance(metadata, dict):
        #     return {
        #         "status": -1,
        #         "msg": "metadata must be dict",
        #     }
        # payload = {
        #     "query": metadata.get("ASSISTANT_ANSWER"),
        #     "user_id": metadata.get("user_id"),
        #     "conversation_id": conversation_id,
        #     "limit": metadata.get("limit"),
        # }
        # async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
        #     async with session.post(
        #         url=f"{str(URL_PIKA_MEMORY)}/search_facts",
        #         headers={"Content-Type": "application/json"},
        #         json=payload,
        #     ) as response:
        #         logging.info(f"[END TOOL] mem0Search {conversation_id} - {await response.text()} - {payload}")
        #         if response.status == 200:
        #             output = await response.json()
        #             if isinstance(output, list):
        #                 for item in output:
        #                     facts_values.append(item.get("fact_value"))
        # # logging.info(f"============[END TOOL] mem0Search {conversation_id} - {facts_values}")
        # if len(facts_values) < 1:
        #     return {
        #         "status": -1,
        #         "msg": "No facts found",
        #     }
        # payload = {
        #     "USER_FACT": json.dumps(facts_values, ensure_ascii=False, indent=4),
        #     "ASSISTANT_ANSWER": metadata.get("ASSISTANT_ANSWER"),
        # }
        # # logging.info(f"============[END TOOL] mem0Search {conversation_id} - {payload}")
        # if not isinstance(payload, dict):
        #     return {
        #         "status": -1,
        #         "msg": "metadata must be dict",
        #     }
        
        # logging.info(f"[START TOOL] {conversation_id} - mem0Generation")
        # output = await tool_executor.mem0_generation.process(
        #     conversation_history=inputs.messages,
        #     metadata=payload,
        # )
        # logging.info(f"[END TOOL] mem0Generation {conversation_id} - {output}")
        # return {
        #     "status": 0,
        #     "result": output,
        #     "msg": "Success"
        # }
        

        conversation_id = inputs.conversation_id
        metadata = inputs.metadata
        payload = {
            "user_id": metadata.get("user_id"),
            "conversation_id": conversation_id,
            "conversation": [
                {"role": "user", "content": metadata.get("ASSISTANT_ANSWER")}
            ]
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                url=f"{str(URL_PIKA_MEMORY)}/generate_response",
                headers={"Content-Type": "application/json"},
                json=payload,
            ) as response:
                logging.info(f"[END TOOL] generate_response {conversation_id} - {await response.text()} - {payload}")
                if response.status == 200:
                    output = await response.json()
                    if output.get("status") == "ok" and output.get("response"):
                        return {
                            "status": 0,
                            "result": output.get("response"),
                            "msg": "Success"
                        }
        return {
            "status": -1,
            "result": None,
            "msg": "Failed to generate response"
        }

    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }
    

@app.post(f"/{ROUTE}/v1/tool/mem0Search")
async def mem0_search(inputs: InputRequest):
    try:
        conversation_id = inputs.conversation_id
        metadata = inputs.metadata
        if not isinstance(metadata, dict):
            return {
                "status": -1,
                "msg": "metadata must be dict",
            }
        logging.info(f"[START TOOL] {conversation_id} - mem0Search")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.post(
                url=f"{str(URL_PIKA_MEMORY)}/search_facts",
                headers={"Content-Type": "application/json"},
                json=metadata,
            ) as response:
                logging.info(f"[END TOOL] mem0Search {conversation_id} - {await response.text()} - {metadata}")
                if response.status == 200:
                    output = await response.json()
                    return {
                        "status": 0,
                        "result": output,
                        "msg": "Success"
                    }
        return {
            "status": -1,
            "result": None,
            "msg": "Failed to search facts"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }


@app.post(f"/{ROUTE}/v1/tool/extractFacts")
async def extract_facts(inputs: InputRequest):
    try:
        metadata = inputs.metadata
        if not isinstance(metadata, dict):
            return {
                "status": -1,
                "msg": "metadata must be dict",
            }
        conversation_id = metadata.get("conversation_id")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                url=f"{str(URL_PIKA_MEMORY)}/extract_facts",
                headers={"Content-Type": "application/json"},
                json=metadata,
            ) as response:
                logging.info(f"[END TOOL] extractFacts {conversation_id} - {await response.text()} - {metadata}")
                if response.status == 200:
                    output = await response.json()
                    return {
                        "status": 0,
                        "result": output,
                        "msg": "Success"
                    }
        return {
            "status": -1,
            "result": None,
            "msg": "Failed to extract facts"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }
    

@app.post(f"/{ROUTE}/v1/tool/summaryConversation")
async def summary_conversation(inputs: InputRequest):
    try:
        conversation_id = inputs.conversation_id
        messages = inputs.messages
        logging.info(f"[START TOOL] {conversation_id} - summaryConversation")
        output = await tool_executor.summary_conversation.process(
            conversation_history=messages,
        )
        logging.info(f"[END TOOL] summaryConversation {conversation_id} - {output}")
        return {
            "status": 0,
            "result": output,
            "msg": "Success"
        }
    except Exception as e:
        return {
            "status": -1,
            "msg": f"Bad request {traceback.format_exc()}",
        }

if __name__ == "__main__":
    uvicorn.run("app:app", host=args.host, port=args.port, workers=args.workers)
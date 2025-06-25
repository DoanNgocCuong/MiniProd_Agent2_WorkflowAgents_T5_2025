import logging, copy, os, traceback
from typing import List
from src.chatbot.llm_base import BaseLLM
import aiohttp, json, time
from src.channel.mysql_bot import MYSQL_BOT


URL_PROFILE = os.getenv("URL_PROFILE")
TOKEN_PROFILE = os.getenv("TOKEN_PROFILE")
TOOL_EXECUTOR_URL = os.getenv("TOOL_EXECUTOR_URL")
URL_WORKFLOW = os.getenv("URL_WORKFLOW") if os.getenv("URL_WORKFLOW") is not None else ""
URL_AGENT = os.getenv("URL_AGENT") if os.getenv("URL_AGENT") is not None else ""


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

def get_provider(provider_name: str, provider_config: dict) -> dict:
    provider_configs = copy.deepcopy(provider_config)
    if isinstance(provider_configs.get(provider_name), dict):
        provider = provider_configs.get(provider_name)
        return provider
    return None


def init_llm_bot_config(provider_models: dict, provider_name: str, bot_config: dict):
    provider = get_provider(provider_name, provider_models)
    if not isinstance(provider, dict):
        logging.error(f"[ERROR] provider_name is not found in config: {provider_name}")
        return None
    output = {}
    output["llm"] = BaseLLM(
        provider.get("openai_setting"),
        provider_name = provider_name,
    )
    output["generation_params"] = copy.deepcopy(provider.get("generation_params"))
    return output


def load_llm_bot_config(provider_models: dict, array_bot_config: List[dict]):
    output = {}
    for name, item in provider_models.items():
        try :
            openai_setting = item.get("openai_setting")
            openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
            output[name] = BaseLLM(
                openai_setting = openai_setting,
                provider_name = name,
            )
        except Exception as e:
            logging.info(f"[ERROR] load_llm_bot_config: {traceback.format_exc()}")
            continue
    return output
    

async def call_api_get_profile_description() -> dict:
    try :
        url=f"{str(URL_PROFILE)}/user_profile_description"
        params = {
            "token": TOKEN_PROFILE
        }
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                logging.info(f"[call_api_get_profile_description]==============: {url} - {params} - {await response.text()}")
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == 200:
                        return data.get("data")
        return None
    except:
        logging.info(f"[ERROR] call_api_get_profile_description: {traceback.format_exc()}")
        return None
    

async def call_api_get_user_profile(conversation_id: str) -> dict:
    try :
        url=f"{str(URL_PROFILE)}/user_profile"
        params = {
            "conversation_id": conversation_id,
            "token": TOKEN_PROFILE
        }
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                logging.info(f"[call_api_get_user_profile]==============: {url} - {params} - {await response.text()}")
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == 200:
                        return data.get("data")
        return None
    except:
        logging.info(f"[ERROR] call_api_get_user_profile: {traceback.format_exc()}")
        return None
    

async def call_api_update_user_profile(payload: dict) -> bool:
    try :
        url=f"{str(URL_PROFILE)}/user_profile"
        headers = {'Content-Type': 'application/json'}
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.put(url, headers=headers, json=payload) as response:
                logging.info(f"[INFO] call_api_update_user_profile: {url} - {payload} - {await response.text()}")
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == 200:
                        return True
        return False
    except:
        return False
    

async def callAPIPropertyMatching(conversation_id: str, bot_id: int, messages: List[dict]) -> dict:
    try :
        start_time = time.time()
        url=f"{str(TOOL_EXECUTOR_URL)}/properityMatching"
        headers = {'Content-Type': 'application/json'}
        timeout = aiohttp.ClientTimeout(total=5)
        payload = {
            "bot_id": bot_id,
            "conversation_id": conversation_id,
            "messages": messages
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                logging.info(f"[INFO] callAPIPropertyMatching: {url} - {await response.text()}")
                if response.status == 200:
                    data = await response.json()
                    MYSQL_BOT.insert_conversation_logging(
                        bot_id=bot_id,
                        conversation_id=conversation_id,
                        input_text=json.dumps(messages),
                        output_text=json.dumps(data.get("result"), ensure_ascii=False),
                        process_time=time.time() - start_time,
                        provider_name="",
                        task_name="callAPIPropertyMatching",
                    )
                    if isinstance(data.get("result"), dict):
                        return data.get("result")
        return None
    except:
        logging.info(f"[ERROR] callAPIPropertyMatching: {traceback.format_exc()}")
        return None
    
    
def parsing_json(text: str) -> dict:
    try :
        if not text:
            return None
        return json.loads(text)
    except:
        return None
    
    
async def async_init_conversation(conversation_id: str, robot_type: str, robot_type_id: int, input_slots: dict, is_tool = False, **kwargs):
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
        user_id = kwargs.get("user_id")
        if user_id is not None:
            payload["user_id"] = user_id
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/initConversation", json=payload, headers=headers, timeout=5) as response:
                logging.info(f"[INIT CALL]================: {url}/initConversation - {payload} - {await response.text()}")
                if response.status == 200:
                    result = await response.json()
                    if isinstance(result, dict) and result.get("status") == 0:
                        return True
        return False
    except Exception as e:
        logging.info(f"[ERROR] async_init_conversation: {traceback.format_exc()}")
        return False


async def async_webhook(conversation_id: str, robot_type: str, message: str, first_message: str = None, **kwargs):
    try :
        start_time = time.time()
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

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/webhook", json=payload, headers=headers, timeout=5) as response:
                logging.info(f"[WEBHOOK]================: {url}/webhook - {payload} - {await response.text()}")
                if response.status == 200:
                    result = await response.json()
                    MYSQL_BOT.insert_conversation_logging(
                        bot_id=kwargs.get("bot_id"),
                        conversation_id=conversation_id,
                        input_text=json.dumps(payload, ensure_ascii=False),
                        output_text=json.dumps(result, ensure_ascii=False),
                        process_time=time.time() - start_time,
                        provider_name="",
                        task_name="async_webhook",
                    )
                    if isinstance(result, dict):
                        return result
        return None
    except Exception as e:
        logging.info(f"[ERROR] async_webhook: {traceback.format_exc()}")
        return None
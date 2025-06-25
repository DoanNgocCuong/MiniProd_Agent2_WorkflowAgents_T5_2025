import logging, copy, os, traceback
import hashlib  # Add this import for SHA-256 hashing
from typing import List
from src.chatbot.llm_base import BaseLLM
import aiohttp


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
    # if not isinstance(array_bot_config, list):
    #     logging.error(f"[ERROR] array_bot_config is not list: {array_bot_config}")
    #     return output
    # for bot_config in array_bot_config:
    #     bot_id = bot_config.get("id")
    #     provider_name = bot_config.get("provider_name")
    #     provider = get_provider(provider_name, provider_models)
    #     if not isinstance(provider, dict):
    #         logging.error(f"[ERROR] provider_name is not found in config: {provider_name}")
    #         continue
    #     if output.get(bot_id) is None:
    #         output[int(bot_id)] = {}
    #     llm_init = init_llm_bot_config(
    #         provider_models=provider_models,
    #         provider_name=provider_name,
    #         bot_config=bot_config
    #     )
    #     if llm_init is not None:
    #         output[int(bot_id)].update(llm_init)

    # bot_id = -1
    # if output.get(bot_id) is None:
    #     output[int(bot_id)] = {}
    # llm_init = init_llm_bot_config(
    #     provider_models=provider_models,
    #     provider_name="openai",
    #     bot_config=None
    # )
    # output[-1].update(llm_init)

    # return output

URL_PROFILE = os.getenv("URL_PROFILE")
TOKEN_PROFILE = os.getenv("TOKEN_PROFILE")

async def call_api_get_profile_description() -> dict:
    try :
        url=f"{str(URL_PROFILE)}/user_profile_description"
        params = {
            "token": TOKEN_PROFILE
        }
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
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
                text = await response.text()
                logging.info(f"====================={url} - {params} - {text}")
                if response.status == 200:
                    data = await response.json()
                    # logging.info(f"=====================data: {data}")
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
            logging.info(f"[INFO] call_api_update_user_profile: {url} - {payload}")
            async with session.put(url, headers=headers, json=payload) as response:
                logging.info(f"[INFO] call_api_update_user_profile: {url} - {await response.text()}")
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == 200:
                        return True
        return False
    except:
        return False


def hash_string_sha256(input_string: str) -> str:
    """
    Hashes a string using SHA-256 with UTF-8 encoding.
    
    Args:
        input_string (str): The string to be hashed
        
    Returns:
        str: The hexadecimal representation of the hash
    """
    try:
        # Encode the string to UTF-8 and create a hash object
        hash_object = hashlib.sha256(input_string.encode('utf-8'))
        # Get the hexadecimal representation of the hash
        hex_digest = hash_object.hexdigest()
        return hex_digest
    except Exception as e:
        logging.error(f"[ERROR] Failed to hash string: {traceback.format_exc()}")
        return ""
    

def get_task_id(bot_id: str, conversation_id: str, input_string: str) -> str:
    """
    Hashes a string using SHA-256 with UTF-8 encoding.
    
    Args:
        input_string (str): The string to be hashed
        
    Returns:
        str: The hexadecimal representation of the hash
    """
    return f"{bot_id}_{conversation_id}_{hash_string_sha256(input_string)}"
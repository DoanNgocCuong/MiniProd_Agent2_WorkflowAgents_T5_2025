import logging, copy, os, traceback
from typing import List
from src.chatbot.llm_base import BaseLLM
import aiohttp

URL_PROFILE = os.getenv("URL_PROFILE")
TOKEN_PROFILE = os.getenv("TOKEN_PROFILE")
WORKFLOW_URL = os.getenv("WORKFLOW_URL")

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
        

async def call_api_get_gifs(bot_id) -> List[str]:
    try :
        url=f"{str(WORKFLOW_URL)}/database/getGifs"
        params = {
            "bot_id": bot_id
        }
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                text = await response.text()
                logging.info(f"=====================call_api_get_gifs {url} - {params} - {text}")
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data.get("gifs"), list) and len(data.get("gifs")) > 0:
                        return data.get("gifs")
        return None
    except:
        logging.info(f"[ERROR] call_api_get_gifs: {traceback.format_exc()}")
        return None
from typing import Dict, List
import aiohttp
import logging, json, os, traceback
from src.utils.utils import call_api_update_user_profile


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class ToolInterface:
    def __init__(self):
        self.url = os.getenv("TOOL_EXECUTOR_URL") + "/execute"
        self.headers = {'Content-Type': 'application/json'}
        self.tool_executor_url = os.getenv("TOOL_EXECUTOR_URL")

    async def process(
        self,
        conversation_id: str,
        tool_name: str,
        audio_url: str = None,
        message: str = None,
        text_refs: str = None,
        question: str = None,
        metadata: dict = None,
        **kwargs
    ) -> Dict[str, str]:
        payload = {
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "audio_url": audio_url if audio_url is not None else "",
            "message": message if message is not None else "",
            "text_refs": text_refs if text_refs is not None else "",
            "question": question if question is not None else "",
            "metadata": metadata if metadata is not None else {},
        }
        try :
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=payload, headers=self.headers, timeout = 5) as response:
                    if response.status == 200:
                        result = await response.json()
                        logging.info(f"[ToolInterface][INFO]: {self.url} - {payload} - {result}")
                        if result.get("status") == 0:
                            return result.get("result")
            return None
        except Exception as e:
            logging.info(f"[ToolInterface][ERROR] {self.url} - {payload} : {traceback.format_exc()}")
            return None
        
    async def call_profile_extraction(
        self,
        conversation_id: str = None,
        messages: List[dict] = None,
        url: str = None,
    ) -> bool:
        try :
            payload = {
                "conversation_id": conversation_id,
                "messages": messages
            }
            user_profile = None
            async with aiohttp.ClientSession() as session:
                logging.info(f"[ToolInterface][INFO]: {self.tool_executor_url}/profileExtraction - {payload}")
                async with session.post(f"{self.tool_executor_url}/profileExtraction", json=payload, headers=self.headers, timeout = 5) as response:
                    if response.status == 200:
                        result = await response.json()
                        logging.info(f"[ToolInterface][INFO]: {self.tool_executor_url}/profileExtraction - {payload} - {result}")
                        if result.get("status") == 0 and isinstance(result.get("result"), dict):
                            user_profile = result.get("result")
                            for key, value in user_profile.items():
                                if not isinstance(value, str):
                                    return False
                                
                if isinstance(user_profile, dict):
                    payload = {
                        "token": os.getenv("TOKEN_PROFILE"),
                        "conversation_id": conversation_id,
                        "data": user_profile,
                    }
                    await call_api_update_user_profile(payload)
                    return True
            return False
        except Exception as e:
            logging.info(f"[ToolInterface][ERROR] {self.url} - {payload} : {traceback.format_exc()}")
            return False
    
    async def aync_call_api(self, url: str, headers: dict, payload: dict, timeout: int = 5, method: str = "POST", task_name: str = "") -> bool:
        try:
            if method == "POST":
                timeout = aiohttp.ClientTimeout(total=timeout)
                logging.info(f"[INFO][TOOL] aync_call_api - {task_name}: {url} - {headers} - {payload}")
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=payload) as response:
                        logging.info(f"[INFO][TOOL] aync_call_api - {task_name}: {url} - {await response.text()}")
                        if response.status == 200:
                            return await response.json()
            if method == "GET":
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers, params=payload) as response:
                        logging.info(f"[INFO][TOOL] aync_call_api - {task_name}: {url} - {await response.text()}")
                        if response.status == 200:
                            return await response.json()
            return None
        except:
            logging.info(f"[ERROR][TOOL] aync_call_api - {task_name}: {traceback.format_exc()}")
            return None
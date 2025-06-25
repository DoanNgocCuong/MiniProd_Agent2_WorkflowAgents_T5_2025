from typing import Dict, List
import aiohttp
import logging, json, os, traceback
from src.utils.utils import call_api_update_user_profile
from src.chatbot.prompt import (
    format_prompt_from_variable, 
    get_system_conversation_history, 
    SYSTEM_PROMPT_EXTRACTION_PROFILE,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.basicConfig(
    level=logging.ERROR,
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
        **kwargs
    ) -> Dict[str, str]:
        payload = {
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "audio_url": audio_url if audio_url is not None else "",
            "message": message if message is not None else "",
            "text_refs": text_refs if text_refs is not None else "",
            "question": question if question is not None else "",
        }
        try :
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, json=payload, headers=self.headers, timeout = 5) as response:
                    logging.info(f"[ToolInterface][INFO]: {self.url} - {payload}")
                    if response.status == 200:
                        result = await response.json()
                        logging.info(f"[ToolInterface][INFO]: {self.url} - {payload} - {result}")
                        if result.get("status") == 0:
                            return result.get("result")
            return None
        except Exception as e:
            logging.info(f"[ToolInterface][ERROR] {self.url} - {payload} : {traceback.format_exc()}")
            return None


    async def request_api_tool(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        payload: Dict[str, str],
        timeout: int = 5,
        audio_url: str = None,
        **kwargs
    ):
        try:
            async with aiohttp.ClientSession() as session:
                logging.info(f"[TOOLS][INFO] Request Tool: {url} - payload: {payload}")
                if audio_url is not None:
                    async with session.get(audio_url) as audio_response:
                        if audio_response.status == 200:
                            audio_data = await audio_response.read()  # Read audio data as bytes

                            # Prepare FormData with the downloaded audio data
                            form_data = aiohttp.FormData()
                            form_data.add_field('audio-file', audio_data, filename=audio_url.split("/")[-1], content_type='audio/wav')
                            form_data.add_field('text-refs', payload['text-refs'])
                            form_data.add_field('token', payload['token'])
                            # Now send the audio file along with payload to the API
                            # logging.info(f"[TOOLS][INFO] Request Tool: {url} - form_data: {form_data}")
                            async with session.post(url, data=form_data, timeout=timeout, headers=headers) as response:
                                response_json = await response.json()
                                return response_json
                else :
                    async with session.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=payload,
                        timeout=timeout
                    ) as response:
                        status = response.status
                        if status != 200:
                            logging.error(f"[TOOLS][ERROR] Request Tool ERROR: {status}")
                            return None
                        response_json = await response.json()
                        return response_json
        except Exception as e:
            logging.error(f"[TOOLS][ERROR] Request Tool ERROR: {traceback.format_exc()}")
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
                async with session.post(f"{self.tool_executor_url}/profileExtraction", json=payload, headers=self.headers, timeout = 30) as response:
                    logging.info(f"[ToolInterface][INFO]: {self.tool_executor_url}/profileExtraction - {payload} - {await response.text()}")
                    if response.status == 200:
                        result = await response.json()
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
            logging.info(f"[ToolInterface][ERROR] {self.tool_executor_url}/profileExtraction - {payload} : {traceback.format_exc()}")
            return False
        
    async def check_call_tool(self, conversation_id: str, messages: List[dict]) -> bool:
        try:
            url = f"{str(self.tool_executor_url)}/checkCallTool"
            headers = {'Content-Type': 'application/json'}
            timeout = aiohttp.ClientTimeout(total=5)
            payload = {
                "conversation_id": conversation_id,
                "messages": messages
            }
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    logging.info(f"[INFO][TOOL] check_call_tool: {url} - {await response.text()}")
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data.get("result"), bool):
                            return data.get("result")
            return False
        except:
            logging.info(f"[ERROR][TOOL] check_call_tool: {traceback.format_exc()}")
            return False
        
    async def aync_call_api(self, url: str, headers: dict, payload: dict, timeout: int = 5, method: str = "POST", task_name: str = "") -> bool:
        try:
            if method == "POST":
                timeout = aiohttp.ClientTimeout(total=timeout)
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
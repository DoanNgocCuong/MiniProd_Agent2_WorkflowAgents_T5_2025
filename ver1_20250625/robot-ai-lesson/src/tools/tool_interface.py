from typing import Dict, List
import aiohttp
import logging, json, os, traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class ToolInterface:


    @staticmethod
    async def process(
        self,
        input: Dict[str, str],
        tool: Dict[str, str],
        timeout: int = 5,
        **kwargs
    ) -> Dict[str, str]:
        raise NotImplementedError("process method must be implemented")


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
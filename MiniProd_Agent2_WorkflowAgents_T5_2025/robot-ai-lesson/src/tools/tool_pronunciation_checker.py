import os, logging, json, traceback
from .tool_interface import ToolInterface

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class ToolsPronunciationChecker(ToolInterface):


    async def process(
        self,
        input: dict,
        tool: dict,
        timeout: int = 5,
        **kwargs
    ) -> dict:
        try:
            url = tool.get("api_config").get('url')
            headers = tool.get("api_config").get('headers')
            payload = {
                "text": input.get('text')
            }
            method = tool.get("api_config").get("method")
            timeout = tool.get("api_config").get("timeout") if isinstance(tool.get("api_config").get("timeout"), int) else timeout
            
            retry = 100
            last_retry_fail_response = None
            if isinstance(tool.get("flow"), dict):
                retry = tool.get("flow").get("retry")
                last_retry_fail_response = tool.get("flow").get("last_retry_fail_response")

            system_repeat = tool.get("SYSTEM_REPEAT")

            params = kwargs.get("params")
            sentence = None
            audio_url = None
            if isinstance(params, dict):
                sentence = params.get("sentence")
                audio_url = params.get("audio_url")

            logging.info(f"[TOOLS][INFO] Tool: params: {params} - Sentence: {sentence} - Audio URL: {audio_url}")
            if sentence is None or audio_url is None:
                return {
                    "text": None,
                    "tool_status": "ERROR", ## PASS OR FAIL
                }

            payload = {
                'text-refs': sentence,
                'token': 'demo_gcxpHQmLeVwLWobE6apU1lgAg49YTM0'
            }

            response = await self.request_api_tool(
                url=url,
                method=method,
                headers=headers,
                payload=payload,
                timeout=timeout,
                audio_url=audio_url
            )
            pronunciation_error = self.extract_pronunciation(data=response)
            output = None
            if pronunciation_error is not None:
                output = "Có lỗi phát âm ở các từ: " + pronunciation_error + ". Em thử nói lại 1 lần nữa nhé!"
            if isinstance(system_repeat, int) and isinstance(retry, int):
                if output is not None and system_repeat >= retry:
                    output = last_retry_fail_response
                    return {
                        "text": output,
                        "tool_status": "FAIL-END", ## PASS OR FAIL
                    }
            # logging.info(f"[TOOLS][INFO] Request Tool: {url} - response: {response}")
            return {
                "text": output,
                "tool_status": "PASS" if output is None else "FAIL", ## PASS OR FAIL
            }
        except Exception as e:
            logging.error(f"[TOOLS][ERROR] Error in process: {traceback.format_exc()}")
            return {
                "text": None,
                "tool_status": "ERROR", ## PASS OR FAIL
            }
        

    def extract_pronunciation(self, data: dict, threshold = 0.7) -> dict:
        try:
            if not isinstance(data, dict):
                return None
            error = []
            word_pronunciation_error = []
            for element in data.get("result"):
                word = element.get("word")
                score = element.get("score")
                if score <= threshold:
                    word_pronunciation_error.append(word)
                    error.append({
                        "word": word,
                        "score": score
                    })
            logging.info(f"[TOOLS][INFO] Pronunciation error: {error}")
            return ", ".join(word_pronunciation_error)
        except Exception as e:
            return None
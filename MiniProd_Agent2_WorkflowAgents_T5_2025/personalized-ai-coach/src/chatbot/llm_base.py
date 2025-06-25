from typing import List
import traceback, copy, os
import logging, json, aiohttp, re, time
from openai import AsyncOpenAI
import google.generativeai as genai
from src.channel.mysql_bot import MYSQL_BOT


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class BaseLLM:
    """`BaseAgent` is a base object of Agent."""

    def __init__(self, openai_setting, provider_name = None, **kwargs):
        self.openai_setting = openai_setting
        self.provider_name = provider_name
        if isinstance(self.openai_setting, dict) and self.provider_name != 'gemini':
            self.client = AsyncOpenAI(
                **openai_setting
            )
        else :
            genai.configure(api_key=openai_setting.get("api_key"))
            self.client = None
        self.system_error = kwargs.get(
            "system_error", 
            "Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau"
        )


    def gemini_preprocess_message(self, messages: List):
        messages_model = copy.deepcopy(messages)
        for idx, message in enumerate(messages_model):
            if message.get("role") in ["system", "assistant"]:
                messages_model[idx]["role"] = "model"
                messages_model[idx]["parts"] = copy.deepcopy(messages_model[idx]["content"])
                if messages_model[idx].get("content") is not None:
                    del messages_model[idx]["content"]
            elif message.get("role") == "user":
                messages_model[idx]["role"] = "user"
                text = copy.deepcopy(messages_model[idx]["content"])
                if text in ["", None]:
                    text = " "
                messages_model[idx]["parts"] = text
                if messages_model[idx].get("content") is not None:
                    del messages_model[idx]["content"]
        return messages_model
            
    
    async def get_response(self, messages: List, params: dict, **kwargs):
        output = None
        try :
            start_time = time.time()
            if self.client is None or self.provider_name == 'gemini':
                model = genai.GenerativeModel(params.get("model"))
                messages_model = self.gemini_preprocess_message(messages)               
                response = model.start_chat(
                    history=messages_model[:-1]
                )
                response = response.send_message(messages_model[-1].get("parts"))
                output = response.text
            else :
                response = await self.client.chat.completions.create(
                    messages=messages,
                    **params
                )
                output = response.choices[0].message.content
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=kwargs.get("conversation_id"),
                input_text=json.dumps(messages, ensure_ascii=False),
                output_text=output,
                process_time=time.time() - start_time,
                provider_name=self.provider_name,
                task_name=kwargs.get("task_name"),
            )
            return output
        except Exception as e:
            return output
    

    async def predict(self, messages, params: List[dict], **kwargs):
        try:
            start_time = time.time()
            format_output = kwargs.get("format_output")
            logging.info(f"[BaseLLM] {kwargs.get('conversation_id')} - Start predict")
            if kwargs.get("first_message") is not None and kwargs.get("start_message") not in [None, ""]:
                res = {
                    "status": "CHAT",
                    "answer": kwargs.get("start_message"),
                    "correct_answer": "NONE",
                    "language": "vi" if kwargs.get("language") is None else kwargs.get("language"),
                    "sentence": None,
                }
                logging.info(f"[BaseLLM] {kwargs.get('conversation_id')} - Predict: {res}")
                MYSQL_BOT.insert_conversation_logging(
                    bot_id=kwargs.get("bot_id"),
                    conversation_id=kwargs.get("conversation_id"),
                    input_text=json.dumps(messages, ensure_ascii=False),
                    output_text=kwargs.get("start_message"),
                    process_time=time.time() - start_time,
                    provider_name="",
                    task_name="AGENT_PREDICTION",
                )
                return res
            res = await self.get_response(
                messages = messages,
                params = params,
                **kwargs
            )
            logging.info(f"[BaseLLM] {kwargs.get('conversation_id')} - Predict: {res}")
            if format_output == "TEXT":
                pattern = r"\bEND(?:\.)?\b"
                matches = re.finditer(pattern, res)
                entities = [{"value": match.group(), "start": match.start(), "end": match.end()} for match in matches]
                if len(entities) > 0:
                    entities = sorted(entities, key=lambda x: x["start"])
                status = "CHAT"
                if len(entities) > 0 and len(res) - entities[-1].get("end") <= 4:
                    entities = sorted(entities, key=lambda x: x["start"])
                    status = "END"
                    res = res[:entities[-1].get("start")]
                res = {
                    "status": status,
                    "answer": res,
                    "correct_answer": "NONE",
                    "language": "vi" if kwargs.get("language") is None else kwargs.get("language"),
                    "sentence": None,
                }
            else :
                res = self.parsing_json(res)
                if not isinstance(res, dict) or res.get("answer") is None or res.get("status") is None:
                    return {
                        "status": "END",
                        "answer": self.system_error,
                        "correct_answer": "NONE",
                    }
            return res
        except:
            logging.error(f"Request failed: {traceback.format_exc()}.")
            return {
                "status": "END",
                "answer": self.system_error,
                "correct_answer": "NONE",
            }
            
    
    def parsing_json(self, data: str) -> dict:
        try:
            try:
                return json.loads(data)
            except ValueError as e:
                output = data.replace("```json\n", "")
                output = output.replace("\n```", "")
                return json.loads(output)
        except Exception as e:
            return data
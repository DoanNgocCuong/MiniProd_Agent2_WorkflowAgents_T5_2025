from typing import List
import traceback, copy, os
import logging, json, aiohttp

from openai import AsyncOpenAI
import google.generativeai as genai


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class LLMBase:
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
            
    
    async def get_response(self, messages: List, **params):
        logging.info(f"=============messages: {json.dumps(messages, indent=4, ensure_ascii=False)}")
        if self.client is None or self.provider_name == 'gemini':
            model = genai.GenerativeModel(params.get("model"))
            messages_model = self.gemini_preprocess_message(messages)               
            response = model.start_chat(
                history=messages_model[:-1]
            )
            response = response.send_message(messages_model[-1].get("parts"))
            return response.text
        else :
            response = await self.client.chat.completions.create(
                messages=messages,
                **params
            )
            return response.choices[0].message.content
        
    async def predict(self, messages: List, params, **kwargs):
        try:
            logging.info(f"[LLMBASE][START] Start predict")
            res = await self.get_response(messages, **params)
            logging.info(f"[LLMBASE][END] END predict: {res}")
            return res
        except Exception as e:
            logging.error(f"[LLMBASE][Error]: {messages} - {traceback.format_exc()}")
            return None
    
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
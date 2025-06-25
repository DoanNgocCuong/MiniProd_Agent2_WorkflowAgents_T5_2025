import os, traceback, copy, json
from .llm_base import LLMBase
from typing import List


class ProfileExtractor:
    def __init__(self, provider_models: dict):
        provider_models_copy = copy.deepcopy(provider_models)
        provider_name=os.getenv("PROVIDER_NAME")
        provider_name = "openai" if not isinstance(provider_name, str) or provider_models_copy.get(provider_name) is None else provider_name
        openai_setting = provider_models_copy.get(provider_name).get("openai_setting")
        openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
        self.generation_params = provider_models_copy.get(provider_name).get("generation_params")
        self.llm = LLMBase(
            openai_setting=openai_setting,
            provider_name=provider_name,
        )

    async def process(self, 
        messages: List[dict],
        **kwargs):
        try:
            if not isinstance(messages, list) or len(messages) == 0:
                return None
            response = await self.llm.get_response(
                messages,
                **self.generation_params)
            return self.parsing_json(response)
        except Exception as e:
            return None
    
    def parsing_json(self, text: str):
        try :
            return json.loads(text)
        except:
            return text
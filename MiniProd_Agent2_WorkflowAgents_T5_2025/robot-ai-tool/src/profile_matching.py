import os, traceback, copy, json
from .llm_base import LLMBase

SYSTEM_PROMPT = """
You are an assistant to find the information field that matches the description provided by the customer.

<task>
Your task is to map the customer's description to match the corresponding field information in the user's profile and return the name of the matched field.
Steps to perform:
Step 1: Read the user's profile data.
Step 2: Review the customer's description to identify which field in the profile matches the description.
Step 3: Return the name of the field that matches the description.
</task>

<profile> 
The user's profile information is organized in JSON format, where the key is the field name, and the value is the field description:
{{profile_description}}
</profile>

<output> 
Return the name of the field that matches the customer's description. 
If no match is found, return the value "NONE" 
The response should only contain the field names from the profile and no other words. 
</output>
"""


class ProfileMatching:
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
        message: str, 
        profile_description: dict = None,
        **kwargs):
        try:
            if not isinstance(profile_description, dict) or len(profile_description) == 0:
                return None
            messages = [
                {
                    "role": "system",
                    "content": copy.deepcopy(SYSTEM_PROMPT).replace("{{profile_description}}", json.dumps(profile_description, ensure_ascii=False, indent=4)),
                }
            ]
            messages.append(
                {
                    "role": "user",
                    "content": message,
                }
            )
            response = await self.llm.get_response(
                messages,
                **self.generation_params)
            if response not in profile_description:
                return None
            return response
        except Exception as e:
            return None
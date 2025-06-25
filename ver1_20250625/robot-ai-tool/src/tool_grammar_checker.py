import os, traceback, copy
from .llm_base import LLMBase

SYSTEM_PROMPT = """
Act as an English grammar teacher. Your task will be:
- Carefully analyze the answer to the question.
- Check if answer is related to question (context is not important)
INSTRUCTION
STEP 1: CHECK
- Check if answer is grammar correct.
- Check if there is any grammar mistake
- Check if answer partly related the question.
- Accept informal vocabulary usage as correct.
- Accept user's answer is correct in every context
 + If answer check is true, do not give any suggestion.
+ If check is false, give correct answer
- Accept correct answer phrase, or extened answer as correct.
- Ignore inccorrect punctuation (. , ! ?...) mistakes as correct.
STEP 2: RESPOND:
- give short, simple, brief explanation, and correct answer if false
+ if answer correct, respond with:
{"explanation":null,"fixed_answer":null,"correct_grammar":"yes"}

+ If answer incorrect, never let fixed_answer:null and respond with:
{"explanation":<talk in Vietnamese, explain in detail why [answer] wrong, and correct grammar, then give example answer sentence>,"fixed_answer":<must give example correct answer, not null>,"correct_grammar":"no"}
- remember to us ' instead of " to wrap text within JSON
"""

MESSAGES = [
  {
    "role": "system",
    "content": SYSTEM_PROMPT
  },
  {
    "role": "user",
    "content": "question: What is the most popular dish in your country?\nanswer: The most popular dish in my country is Pizza. You should try when you can!"
  },
  {
    "role": "assistant",
    "content": "{\"fixed_answer\":null,\"explanation\":null\"correct_grammar\":\"yes\"}"
  },
  {
    "role": "user",
    "content": "question: How long have you been working there?\nanswer: I work there for 5 years."
  },
  {
    "role": "assistant",
    "content": "{\"explanation\":\"Ở đây bạn cần sử dụng thì hiện tại hoàn thành tiếp diễn (present perfect continuous) để diễn tả thời gian bạn đã làm việc tại đó từ quá khứ đến hiện tại. Vì vậy câu trả lời đúng sẽ là I have been working there for 5 years.\",\"fixed_answer\":\"I have been working there for 5 years.\",\"correct_grammar\":\"no\"}"
  }
]


class ToolGrammarChecker:
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
        question: str = None,
        **kwargs):
        try:
            messages = copy.deepcopy(MESSAGES)
            messages.append(
                {
                    "role": "user",
                    "content": f"question: {question}\nanswer: {message}"
                }
            )
            response = await self.llm.get_response(
                messages,
                **self.generation_params)
            res = self.llm.parsing_json(response)
            if isinstance(res, dict):
                if res.get("correct_grammar") == "yes":
                    return {}
                return res
            return {
                "msg": res,
            }
        except Exception as e:
            return {
                "msg": f"Bad request {traceback.format_exc()}",
            }
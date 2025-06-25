import os, traceback, copy
from .llm_base import LLMBase
import logging, json


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class CheckCallTool:
    def __init__(self, provider_models: dict):
        """
        Khởi tạo class CheckCallTool với các cấu hình provider model
        
        Args:
            provider_models (dict): Dictionary chứa thông tin cấu hình của các model
        """
        provider_models_copy = copy.deepcopy(provider_models)
        provider_name = "gemini"
        provider_name = "openai" if not isinstance(provider_name, str) or provider_models_copy.get(provider_name) is None else provider_name
        openai_setting = provider_models_copy.get(provider_name).get("openai_setting")
        openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
        self.generation_params = provider_models_copy.get(provider_name).get("generation_params")
        self.llm = LLMBase(
            openai_setting=openai_setting,
            provider_name=provider_name,
        )
        
        # System prompt for tool call detection
        self.system_prompt = """
        You are an assistant tasked with determining whether a tool should be called based on the conversation context. 
        I will use tool check grammar and check pronunciation to check if the User's statement is correct.
        The tool should be called if and only if the user speaks in English, and the user's response needs to slightly align with the question's intent to be considered correct.
        Even if there are grammatical errors, the User's statement is still considered to be correct. 

        <task>
        Step 1: Identify the User's last statement.
        Step 2: Identify the Assistant's question.
        Step 3: Check if the User's statement is in English.
        Step 4: If there are grammatical errors and user's response needs to slightly align with the question's intent to be considered correct.
        Step 5: If the User's statement is in English and correctly answers the Assistant's question, return True. Otherwise, return False.
        </task>

        <think>
        ## Conversation
        Assistant: Tìm kiếm thông tin về Python programming
        User: Yes, I can help you with that.
        
        ## Reasoning
        Step 1: Identify the User's last statement -> Yes, I can help you with that.
        Step 2: Identify the Assistant's question -> Tìm kiếm thông tin về Python programming
        Step 3: Check if the User's statement is in English -> True
        Step 4: If there are grammatical errors and user's response needs to slightly align with the question's intent to be considered correct. -> correct intent
        Step 5: If the User's statement is in English and correctly answers the Assistant's question, return True. Otherwise, return False. -> True
        </think>

        <example>
        ## Conversation
        Assistant: Hôm nay thời tiết thế nào?
        User: Tôi sẽ kiểm tra thời tiết cho bạn.
        
        ## Reasoning
        Step 1: Identify the User's last statement -> Tôi sẽ kiểm tra thời tiết cho bạn.
        Step 2: Identify the Assistant's question -> Tôi sẽ kiểm tra thời tiết cho bạn.
        Step 3: Check if the User's statement is in English -> False
        Step 4: If there are grammatical errors and user's response needs to slightly align with the question's intent to be considered correct. -> incorrect intent
        Step 5: If the User's statement is in English and correctly answers the Assistant's question, return True. Otherwise, return False. -> False
        
        ## Response
        False
        </example>
        
        <example>
        ## Conversation
        Assistant: Hôm nay thời tiết thế nào?
        User: Today It are sunny and warm.
        
        ## Reasoning
        Step 1: Identify the User's last statement -> Today It are sunny and warm.
        Step 2: Identify the Assistant's question -> Hôm nay thời tiết thế nào?
        Step 3: Check if the User's statement is in English -> True
        Step 4: If there are grammatical errors and user's response needs to slightly align with the question's intent to be considered correct. -> Wrong grammar but correct intent
        Step 5: If the User's statement is in English and correctly answers the Assistant's question, return True. Otherwise, return False. -> True
        
        ## Response
        True
        </example>
        
        <output>
            The result should be returned as plain text.
            Only return True or False.
            Do not include reasoning or explanation in the response.
        </output>
        """

    async def process(self, conversation_history: list = None, current_query: str = None, **kwargs):
        """
        Xử lý yêu cầu kiểm tra xem có nên gọi tool hay không dựa trên context
        
        Args:
            conversation_history (list, optional): Lịch sử cuộc trò chuyện
            current_query (str, optional): Câu query hiện tại của user
            
        Returns:
            dict: Kết quả kiểm tra tool call hoặc None nếu có lỗi
        """
        try:
            # Kiểm tra input
            if not conversation_history or not isinstance(conversation_history, list):
                conversation_history = []
            
            # Chuẩn bị messages cho API
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
            
            # Thêm lịch sử cuộc trò chuyện và query hiện tại
            content = []
            for message in conversation_history:
                if message.get("role") == "user":
                    content.append("User: " + message.get("content"))
                if message.get("role") == "assistant":
                    content.append("Assistant: " + message.get("content"))
            
            content = "\n".join(content)
            
            messages.append(
                {
                    "role": "user",
                    "content": content
                }
            )
            
            # Gọi API để lấy kết quả
            response = await self.llm.get_response(
                messages,
                **self.generation_params
            )
            logging.info(f"[CheckCallTool]=============== response: {[response]}")
            
            if not response:
                return False
            
            if isinstance(response, str) and response.rstrip().lower() == "true":
                return True
            else:
                return False
                
        except Exception as e:
            logging.error(f"[CheckCallTool]=============== Error: {traceback.format_exc()}")
            return False

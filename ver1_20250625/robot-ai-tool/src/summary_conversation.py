import os, traceback, copy
from .llm_base import LLMBase
import logging, json


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class SummaryConversation:
    def __init__(self, provider_models: dict):
        """
        Khởi tạo class SummaryConversation với các cấu hình provider model
        
        Args:
            provider_models (dict): Dictionary chứa thông tin cấu hình của các model
        """
        provider_models_copy = copy.deepcopy(provider_models)
        provider_name = os.getenv("PROVIDER_NAME")
        provider_name = "openai" if not isinstance(provider_name, str) or provider_models_copy.get(provider_name) is None else provider_name
        openai_setting = provider_models_copy.get(provider_name).get("openai_setting")
        openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
        self.generation_params = provider_models_copy.get(provider_name).get("generation_params")
        self.llm = LLMBase(
            openai_setting=openai_setting,
            provider_name=provider_name,
        )
        
        # System prompt for language detection
        self.system_prompt = """
        You are a professional AI assistant capable of analyzing and summarizing conversations.

        <task>
        - Carefully read the provided conversation below between "user" and "assistant".
        - Generate a concise summary in plain text format.
        - Clearly highlight the key points, main topics, and user's intent discussed in the conversation.
        - Maintain a neutral and objective tone.
        </task>

        <input>
        - The conversation is provided as a list of JSON objects. Each object represents a conversational turn, with keys as "user" or "assistant" and values as the corresponding utterances.
        </input>

        <output>
        - Return only the summary content of the conversation; do not generate any additional words outside of the summary.
        - Output format: Plain text.
        </output>
        """

    async def process(self, conversation_history: list = None, **kwargs):
        """
        Xử lý yêu cầu tóm tắt cuộc trò chuyện
        
        Args:
            conversation_history (list, optional): Lịch sử cuộc trò chuyện
            
        Returns:
            str: Nội dung tóm tắt cuộc trò chuyện
        """
        try:
            # Kiểm tra xem có lịch sử cuộc trò chuyện không
            if not conversation_history or not isinstance(conversation_history, list):
                return None  # Mặc định trả về None nếu không có lịch sử
            
            # Chuẩn bị messages cho API
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": json.dumps(conversation_history, ensure_ascii=False, indent=4)
                }
            ]
            
            # Gọi API để lấy kết quả
            response = await self.llm.get_response(
                messages,
                **self.generation_params
            )
            logging.info(f"[SummaryConversation]=============== response: {response}")
            
            if not response:
                return None  # Mặc định trả về None nếu không có phản hồi
            
            # Xử lý kết quả
            response = response.strip().lower()
            
            return response
                
        except Exception as e:
            logging.error(f"[SummaryConversation]=============== Error: {traceback.format_exc()}")
            return None  # Mặc định trả về None nếu có lỗi

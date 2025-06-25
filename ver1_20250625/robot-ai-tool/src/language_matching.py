import os, traceback, copy
from .llm_base import LLMBase
import logging, json


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class LanguageMatching:
    def __init__(self, provider_models: dict):
        """
        Khởi tạo class LanguageMatching với các cấu hình provider model
        
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
            You are a classifier that OUTPUTS exactly one token: "en" or "vi".
            DECISION RULES  (apply top-down; stop at first match)
            1. If A_last explicitly requests the Vietnamese meaning / translation
            (keywords: "nghĩa là gì", "tiếng Việt", "dịch sang tiếng Việt", etc.)
            → output "vi".
            2. If A_last instructs the learner to SAY / REPEAT / SPELL / READ
            **a quoted English word or phrase**
            • pattern: /["‘""‘’][A-Za-z]+["‘""‘’]/
            • verbs accepted (English or Vietnamese): say, repeat, spell, read, type,
                "nói", "nhắc lại", "đọc", "đánh vần", "gõ", etc.
            → output "en".
            3. If A_last explicitly tells the learner to answer **in English**
            (phrases: "answer in English", "hãy trả lời bằng tiếng Anh", etc.)
            → output "en".
            4. If A_last explicitly tells the learner to answer **in Vietnamese**
            → output "vi".
            5. A trigger in response ask user talk in english
            → output "en"
            6. A trigger in response ask user talk in vietnamese
            → output "vi"
            OUTPUT FORMAT
            Return ONLY the lowercase string "en" or "vi". No extra text.
        """

    async def process(self, conversation_history: list = None, **kwargs):
        """
        Xử lý yêu cầu xác định ngôn ngữ phù hợp cho câu trả lời dựa trên câu hỏi của Assistant
        
        Args:
            conversation_history (list, optional): Lịch sử cuộc trò chuyện
            
        Returns:
            str: Mã ngôn ngữ ("en" hoặc "vi") hoặc None nếu có lỗi
        """
        try:
            # Kiểm tra xem có lịch sử cuộc trò chuyện không
            if not conversation_history or not isinstance(conversation_history, list):
                return "en"  # Mặc định trả về tiếng Anh nếu không có lịch sử
            
            # Chuẩn bị messages cho API
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
            
            # Thêm lịch sử cuộc trò chuyện
            content = []
            for message in conversation_history:
                if message.get("role") == "user":
                    content.append("User: " + message.get("content"))
                if message.get("role") == "assistant":
                    content.append("Assistant: " + message.get("content"))
            
            if not content:
                return "en"  # Mặc định trả về tiếng Anh nếu không có nội dung
            
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
            logging.info(f"[LanguageMatching]=============== response: {response}")
            
            if not response:
                return "en"  # Mặc định trả về tiếng Anh nếu không có phản hồi
            
            # Xử lý kết quả
            response = response.strip().lower()
            
            # Trả về kết quả
            if response == "vi":
                return "vi"
            else:
                return "en"  # Mặc định trả về tiếng Anh cho các trường hợp khác
                
        except Exception as e:
            logging.error(f"[LanguageMatching]=============== Error: {traceback.format_exc()}")
            return "en"  # Mặc định trả về tiếng Anh nếu có lỗi

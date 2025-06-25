import os, traceback, copy
from .llm_base import LLMBase
import logging, json
import re
import copy


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class Mem0Generation:
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
        Nhiệm vụ: Cá nhân hóa câu trả lời của trợ lý dựa trên thông tin thực tế đã biết về người dùng.

        ## Bối cảnh:
        - Câu trả lời gốc của trợ lý: {ASSISTANT_ANSWER}
        - Thông tin thực tế về người dùng (Fact): {USER_FACT}

        ## Yêu cầu:
        - Vui lòng viết lại "Câu trả lời gốc của trợ lý" để tích hợp "Thông tin thực tế về người dùng" một cách tự nhiên và phù hợp. Mục tiêu là làm cho câu trả lời mang tính cá nhân hơn bằng cách thể hiện sự hiểu biết về sở thích của người dùng, đồng thời vẫn giữ nguyên ý nghĩa cốt lõi và thông tin chính của câu trả lời gốc.
        - Nếu câu trả lời trợ lý đang bằng tiếng anh thì câu viết lại bằng tiếng anh. Ngược lại nếu tiếng việt thì viết lại cũng là tiếng việt


        ## Kết quả mong muốn:
        - Trả Cung cấp câu trả lời đã được cá nhân hóa
        - Thông tin trả về chỉ được chưas nội dung câu trả lời không chưa ký tự nào khác.
        """

    async def process(self, conversation_history: list = None, **kwargs):
        """
        Args:
            conversation_history (list): Lịch sử cuộc trò chuyện
            **kwargs: Các tham số khác

        Returns:
            str: Câu trả lời đã được cá nhân hóa
        """
        try:
            metadata = kwargs.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("ASSISTANT_ANSWER") is None or metadata.get("USER_FACT") is None:
                return None
            system_prompt = copy.deepcopy(self.system_prompt)
            output = await self.llm.get_response(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt.format(
                            ASSISTANT_ANSWER=metadata.get("ASSISTANT_ANSWER"),
                            USER_FACT=metadata.get("USER_FACT"),
                        )
                    }
                ],
                **self.generation_params
            )
            return output
        except Exception as e:
            logging.error(f"[LanguageMatching]=============== Error: {traceback.format_exc()}")
            return "en"  # Mặc định trả về tiếng Anh nếu có lỗi

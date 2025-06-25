import os, traceback, copy, aiohttp
from .llm_base import LLMBase
from .prompts import SYSTEM_PROMPT_IMAGE_MATCHING
import logging, json
import re


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


REGEX_PATTERN = [
    "nhìn lên màn hình|nhìn vào màn hình|nhìn màn hình|nhìn lên ảnh|nhìn vào ảnh|xem hình|xem ảnh|nhìn hình|quan sát hình|quan sát ảnh|cùng nhìn hình|cùng xem hình|nhìn hình này|nhìn bức hình này|cùng nhìn lên ảnh|look at the screen|look up at the screen|look at the picture|look at the image|look at this picture|look at this image|let's look at the screen|let's look at the picture|take a look at the screen|take a look at the picture|look here|can you see the picture|do you see this image|observe the image|observe the picture"
]


class ImageMatching:
    def __init__(self, provider_models: dict):
        """
        Khởi tạo class ImageMatching với các cấu hình provider model
        
        Args:
            provider_models (dict): Dictionary chứa thông tin cấu hình của các model
        """
        provider_models_copy = copy.deepcopy(provider_models)
        provider_name = os.getenv("PROVIDER_NAME")
        provider_name = "openai" if not isinstance(provider_name, str) or provider_models_copy.get(provider_name) is None else provider_name
        openai_setting = provider_models_copy.get(provider_name).get("openai_setting")
        openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
        self.generation_params = provider_models_copy.get(provider_name).get("generation_params")
        self.generation_params["model"] = "gpt-4o"
        self.llm = LLMBase(
            openai_setting=openai_setting,
            provider_name=provider_name,
        )

    async def process(self,
        bot_id: int = None,
        conversation_history: list = None,
        **kwargs):
        """
        Xử lý yêu cầu tìm kiếm hình ảnh phù hợp với câu hỏi
        
        Args:
            image_list (list): Danh sách các hình ảnh và mô tả
                Mỗi phần tử trong danh sách có dạng:
                {
                    "image_id": "id của hình ảnh",
                    "image_description": "mô tả của hình ảnh"
                }
            conversation_history (list, optional): Lịch sử cuộc trò chuyện
            
        Returns:
            dict: Kết quả phân tích, bao gồm image_id phù hợp nhất hoặc thông báo lỗi
        """
        try:
            image_list = await self.callAPIGetImage(bot_id)
            if not image_list:
                return None
            logging.info(f"===============[ImageMatching] image_list: {image_list}")
            # Chuẩn bị danh sách hình ảnh để đưa vào prompt
            image_list_description = self.get_image_list_description(image_list)
            
            # Tạo system prompt với danh sách hình ảnh
            system_prompt = SYSTEM_PROMPT_IMAGE_MATCHING.replace("{{IMAGE_LIST_DESCRIPTION}}", json.dumps(image_list_description, ensure_ascii=False, indent=4))
            
            # Chuẩn bị messages cho API
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]
            
            # Thêm lịch sử cuộc trò chuyện nếu có
            content = []
            if conversation_history and isinstance(conversation_history, list):
                last_message = conversation_history[-1].get("content")
                regex_status = self.regex(last_message)
                logging.info(f"===============[ImageMatching] regex_status: {regex_status}")
                if regex_status != True:
                    return None
                content = []
                for message in conversation_history:
                    if message.get("role") == "user":
                        content.append("User: " + message.get("content"))
                    if message.get("role") == "assistant":
                        content.append("Assistant: " + message.get("content"))
            if not content:
                return None
            content = "\n".join(content)
            # Thêm câu hỏi hiện tại
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
            logging.info(f"===============[ImageMatching] response: {response}")
            if not response:
                return None
            
            # Xử lý kết quả
            response = response.strip()
            
            # Trả về kết quả
            if response == "NONE" or not response.isdigit():
                return None
            else:
                idx = int(response)
                if idx < len(image_list):
                    return image_list[idx].get("image")
                else:
                    return None
                
        except Exception as e:
            logging.error(f"===============[ImageMatching] Error: {traceback.format_exc()}")
            return None


    def get_image_list_description(self, image_list: list) -> list:
        image_list_description = []
        if len(image_list) == 0:
            return image_list_description
        for idx, value in enumerate(image_list):
            image_list_description.append(
                {
                    "image_id": idx,
                    "image_description": value.get('description'),
                }
            )
        return image_list_description

    async def callAPIGetImage(self, bot_id: int) -> list:
        try:
            async with aiohttp.ClientSession() as session:
                url = os.getenv("URL_IMAGE_DESCRIPTION")
                params = {
                    "token": os.getenv("TOKEN_IMAGE_DESCRIPTION"),
                    "bot_id": bot_id
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict) and isinstance(data.get("data"), dict):
                            return data.get("data").get("images")
                        else:
                            return []
                    else:
                        logging.error(f"Failed to get images. Status: {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Error getting images: {str(e)}")
            return None
        
    
    def regex(self, message: str) -> bool:
        """
        Kiểm tra xem tin nhắn có khớp với các mẫu pattern không
        
        Args:
            message (str): Tin nhắn cần kiểm tra
            
        Returns:
            bool: True nếu tin nhắn khớp với ít nhất một mẫu trong REGEX_PATTERN, False nếu không
        """
        if not message or not isinstance(message, str):
            return False
            
        message = message.lower().strip()
        
        for pattern in REGEX_PATTERN:
            pattern_compiled = re.compile(pattern, re.IGNORECASE)
            if pattern_compiled.search(message):
                return True
        return False
        
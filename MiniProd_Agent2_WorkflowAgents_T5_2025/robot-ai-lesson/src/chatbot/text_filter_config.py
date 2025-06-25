"""
Configuration for text filtering.
This file contains the list of words to filter and fixed responses for incorrect inputs.
"""

# Words and phrases to filter out
FILTERED_WORDS = [
    "lala school",
    "nghiền mì gõ",
    # Add more filtered words here
]

# Fixed responses for incorrect inputs
FIXED_RESPONSES = {
    "default": "Tôi không hiểu ý bạn. Vui lòng thử lại.",
    "too_short": "Vui lòng nhập ít nhất 2 ký tự.",
    "special_chars": "Vui lòng nhập văn bản hợp lệ.",
    "lala_school": ["Tớ chưa nghe rõ, cậu nhắc lại to hơn 1 chút cho Pika nghe nha", "Cậu nhắc lại câu trả lời cho Pika nghe rõ hơn nha"],
    "nghien_mi_go":  ["Tớ chưa nghe rõ, cậu nhắc lại to hơn 1 chút cho Pika nghe nha", "Cậu nhắc lại câu trả lời cho Pika nghe rõ hơn nha"],
    # Add more specific responses for different cases
}

# Maximum number of inputs to track per conversation
MAX_HISTORY_PER_CONVERSATION = 10 
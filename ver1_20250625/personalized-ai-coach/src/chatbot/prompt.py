from typing import List
import copy
import json
import re, logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def format_prompt_from_variable(prompt: List[dict], variables: dict):
    variables_format = copy.deepcopy(variables)
    prompt_format = copy.deepcopy(prompt)
    if not isinstance(prompt_format, list) or len(prompt_format) == 0:
        return prompt_format
    # for idx, element in enumerate(prompt_format):
    #     for _ in range(2):
    #         for key, value in element.items():
    #             for k, v in variables_format.items():
    #                 text = '{{' + k + '}}'
    #                 if prompt_format[idx][key].find(text) != -1 and v is not None:
    #                     prompt_format[idx][key] = copy.deepcopy(prompt_format[idx][key].replace(text, str(v)))
    for idx, element in enumerate(prompt_format):
        for _ in range(2):
            for key, value in element.items():
                prompt_format[idx][key] = format_text_from_input_slots(
                    input_slots=variables,
                    text=value
                )
    return prompt_format


def format_text_from_input_slots(input_slots: dict, text: str):
    if not isinstance(input_slots, dict) or not isinstance(text, str):
        return text
    text = re.sub(r'\s+', ' ', text)
    slots = regex_slot_in_text(
        text=text
    )
    for slot in slots:
        value = get_value_of_slot_from_input(
            slot=slot,
            input_slots=input_slots,
        )
        if value is not None:
            text = text.replace("{{" + slot + "}}", str(value))
    return text


def regex_slot_in_text(text: str):
    if not isinstance(text, str):
        return []
    pattern = r"\{\{([^\{\}]+)\}\}"
    matches = re.findall(pattern, text)
    return [match for match in matches]
    

def get_value_of_slot_from_input(slot: str, input_slots: dict):
    sub_slots = slot.split("/")
    values = copy.deepcopy(input_slots)
    for sub in sub_slots:
        if isinstance(values, dict) and values.get(sub) is not None:
            values = values.get(sub)
        else :
            if isinstance(values, list) and sub.isdigit() == True:
                values = values[int(sub)]
            else :
                return None
    return values


def get_system_conversation_history(history: List[str]):
    conversation_history = []
    for idx, element in enumerate(history):
        if element.get("role") == "user":
            conversation_history.append(f'User: {element.get("content")}')
        if element.get("role") == "assistant":
            try :
                content = json.loads(element.get("content"))
                content = content.get("answer")
            except:
                content = element.get("content")
            conversation_history.append(f'Assistant: {content}')
    return "\n".join(conversation_history)
            
    

# def format_history_from_variable(history: List[str], prompt_variables: dict, **kwargs):
#     history_format = copy.deepcopy(history)
#     bot_config_format = copy.deepcopy(bot_config)
#     variables = copy.deepcopy(prompt_variables)
#     SYSTEM_ARRAY_STEP_ID = []
#     SYSTEM_ARRAY_STEP_TITLE_AND_CONTENT = []
#     for step in bot_config_format.get("scenario"):
#         if step.get("step_id") == step_id:
#             SYSTEM_CONTENT_STEP = f"{step.get('step_id')}: {step.get('title')}\n{step.get('content')}"
#             variables["SYSTEM_CONTENT_STEP"] = SYSTEM_CONTENT_STEP
#         SYSTEM_ARRAY_STEP_ID.append(f'{step.get("step_id")}')
#         SYSTEM_ARRAY_STEP_TITLE_AND_CONTENT.append(f'- {step.get("step_id")}: {step.get("title")}')
#     SYSTEM_ARRAY_STEP_ID = ", ".join(SYSTEM_ARRAY_STEP_ID)
#     SYSTEM_ARRAY_STEP_TITLE_AND_CONTENT = "\n".join(SYSTEM_ARRAY_STEP_TITLE_AND_CONTENT)
#     variables["SYSTEM_ARRAY_STEP_ID"] = SYSTEM_ARRAY_STEP_ID
#     variables["SYSTEM_ARRAY_STEP_TITLE_AND_CONTENT"] = SYSTEM_ARRAY_STEP_TITLE_AND_CONTENT
#     prompt = bot_config_format.get("prompt")
#     prompt = format_prompt_from_variable(prompt, variables)
#     if not isinstance(history_format, list) or len(history_format) == 0:
#         history_format = []
#         history_format = prompt
#     else :
#         history_format[:len(prompt)] = prompt
#     return history_format


# SYSTEM_PROMPT = """
# Vai trò và Mục tiêu: Bạn là trợ lý ảo để hỗ trợ học sinh học tiếng anh bằng cách hoàn thành nhiệm vụ được giao. Nhiệm vụ của bạn là giúp học sinh hiểu và thực hiện các bước để hoàn thành nhiệm vụ. Bạn sẽ nhận được các thông tin từ học sinh và trả lời theo nhiệm vụ đã được giao.


# The response must be in valid JSON format as follows:
# {
#     "status": Trạng thái hoàn thành nhiệm vụ đó có 2 trạng thái (CHAT hoặc END). Với CHAT là tiếp tục cuộc trò chuyện, END là kết thúc cuộc trò chuyện,
#     "answer": Câu trả lời của virtual assistant,
#     "correct_answer": Biểu thị trạng thái tại nhiệm vụ 1, 2, 3, ... với 3 trạng thái (TRUE, FALSE, NONE). Với TRUE là học sinh trả lời đúng câu hỏi, FALSE là học sinh trả lời sai câu hỏi, NONE là trường hợp hỏi học sinh trả lời câu hỏi "đã sẵn sàng chưa",
#     "language": Ngôn ngữ yêu cầu User phải trả lời có 2 ngôn ngữ (vi, en). Với vi là tiếng việt, en là tiếng anh,
#     "sentence": Trích rút câu user cần phải nói đúng với ngôn ngữ tiếng anh (en)
# }


# ## Mô tả nhiệm vụ
# {{SYSTEM_TASK_DESCRIPTION}}


# ## Conversation End
# - End the call when appropriate.
# - Upon customer's closing response, bye customer and response: {"status": "END", "answer": Câu trả lời của virtual assistant, "correct_answer": "TRUE", "language": "en", "sentence": Trích rút câu user cần phải nói đúng với ngôn ngữ tiếng anh}
# - Any subsequent message will start a new call.


# ## Lưu ý Quan trọng
# Giao tiếp với khách hàng bằng tiếng Việt
# Tin nhắn đầu tiên chỉ để khởi tạo nội dung mới cho cuộc gọi, không có ý nghĩa về mặt nội dung
# """

SYSTEM_PROMPT = """
Vai trò và Mục tiêu: Bạn là trợ lý ảo để hỗ trợ học sinh học tiếng anh bằng cách hoàn thành nhiệm vụ được giao. Nhiệm vụ của bạn là giúp học sinh hiểu và thực hiện các bước để hoàn thành nhiệm vụ. Bạn sẽ nhận được các thông tin từ học sinh và trả lời theo nhiệm vụ đã được giao.


The response must be in valid JSON format as follows:
{
    "status": "CHAT/END",          // CHAT to continue, END to finish conversation
    "answer": "Assistant reply",    // Response to student
    "correct_answer": "TRUE/FALSE/NONE",  // Biểu thị trạng thái tại nhiệm vụ 1, 2, 3, ... với 3 trạng thái (TRUE, FALSE, NONE). Với TRUE là học sinh trả lời đúng câu hỏi, FALSE là học sinh trả lời sai câu hỏi, NONE là trường hợp hỏi học sinh trả lời câu hỏi "đã sẵn sàng chưa",
    "language": "vi/en",           // vi=Vietnamese, en=English for Target English sentence student should say
    "sentence": "English text"      // Target English sentence student should say
}


## Mô tả nhiệm vụ
{{SYSTEM_TASK_DESCRIPTION}}


## Conversation End
- End when tasks complete or student indicates finish
- Send farewell with END status
- Reset for new conversation on next message


## Lưu ý Quan trọng
Giao tiếp với khách hàng bằng tiếng Việt
Tin nhắn đầu tiên chỉ để khởi tạo nội dung mới cho cuộc gọi, không có ý nghĩa về mặt nội dung
"""


SYSTEM_PROMPT_EXTRACTIONS = """
## You are an assistant that performs both information extraction and generates sentences or paragraphs based on the given input, using natural language.


## Format for information extraction:
<variable_name> : <Description information extract>


## Extract the following information:
{{SYSTEM_EXTRACTION_VARIABLES}}


## Expected output:
- The information should be returned in JSON format as shown below: {
	"<variable_name>" : , # String value extraction
}

"""

SYSTEM_PROMPT_EXTRACTION_PROFILE = """
## You are an assistant that performs both information extraction and generates sentences or paragraphs based on the given input, using natural language.


## Format for information extraction:
<variable_name> : <Description information extract>


## Extract the following information:
{{SYSTEM_EXTRACTION_PROFILE}}


## Expected output:
- The information should be returned in JSON format as shown below: {
	"<variable_name>" : , # String value extraction
}

"""


PROMPT_VARIABLES = {
    "SYSTEM_PROMPT": SYSTEM_PROMPT,
    "SYSTEM_PROMPT_EXTRACTIONS": SYSTEM_PROMPT_EXTRACTIONS,
}
from typing import List
import copy
import json, re


def format_prompt_from_variable(prompt: List[dict], variables: dict):
    variables_format = copy.deepcopy(variables)
    prompt_format = copy.deepcopy(prompt)
    if not isinstance(prompt_format, list) or len(prompt_format) == 0:
        return prompt_format
    for idx, element in enumerate(prompt_format):
        for _ in range(2):
            for key, value in element.items():
                for k, v in variables_format.items():
                    text = '{{' + k + '}}'
                    if isinstance(prompt_format[idx][key], str) and prompt_format[idx][key].find(text) != -1 and v is not None:
                        prompt_format[idx][key] = copy.deepcopy(prompt_format[idx][key].replace(text, str(v)))
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
                return slot
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


SYSTEM_PROMPT = """
You are an assistant for teaching and learning English. Your task is to classify the intent of the user's utterance based on the intent list provided in the question

<task>
Step 1: Read the assistant's question and user's utterance.
Step 2: Based on the information describing the customer's intent, determine which intent category the answer belongs to from the list below. If it doesn't match any intent, classify it as a "fallback" intent.
Step 3: Return the intent name.
</task>

<tag>
## Descripble intent list
{{SYSTEMT_INTENT_DESCRIPTION}}
</tag>


<ouput>
The result should return only one intent that best matches the customer's response.
The returned intent must belong to one of the intent lists mentioned above.
Only the intent name should be generated, no other characters are allowed.
</ouput>
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
import copy, json, logging
from typing import List, Dict
from src.chatbot.prompt import SYSTEM_PROMPT, format_prompt_from_variable, get_system_conversation_history, SYSTEM_PROMPT_EXTRACTIONS
from src.chatbot.llm_base import BaseLLM
from src.tools.tool_interface import ToolInterface
from src.tools.tool_config import TOOL_OBJECTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class PipelineTask:

    
    def __init__(self):
        self.prompt = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]
        self.res_error = {
            "status": "END",
            "answer": "Xin lỗi, hiện tại hệ thống đang trong quá trình bảo trì và nâng cấp, anh chị vui lòng liên hệ lại sau",
        }


    async def process(
        self, 
        text: str, 
        task_idx: int, 
        history_task: List[list], 
        task_chain: List[dict], 
        llm_base: BaseLLM, 
        generation_params: dict,
        **kwargs
    ) -> List[dict]:
        response = {
            "status": None,
            "answer": [],
            "correct_answer": "NONE",
            "language": "vi",
            "sentence": None,
        }
        format_output = kwargs.get("format_output")
        system_context_variables = kwargs.get("system_context_variables", {})
        if system_context_variables is None:
            system_context_variables = {}
        max_loop = 5
        if task_idx >= len(task_chain):
            return history_task, task_idx, self.res_error
        if isinstance(kwargs.get("history"), list) and len(kwargs.get("history")) > 0:
            history_task[task_idx] = kwargs.get("history")
        loop_idx = 0
        while task_idx < len(task_chain):
            loop_idx += 1
            if loop_idx > max_loop:
                break
            task = copy.deepcopy(task_chain[task_idx])
            for key in system_context_variables:
                if system_context_variables.get(key) is not None:
                    task[key] = copy.deepcopy(system_context_variables.get(key))
            history = copy.deepcopy(history_task[task_idx])
            # logging.info(f"[PipelineTask] pre history: {history}")
            if not isinstance(history, list) or len(history) == 0:
                history = copy.deepcopy(self.prompt)
                system_prompt = kwargs.get("system_prompt")
                if system_prompt not in ["", None]:
                    history[0]["content"] = copy.deepcopy(system_prompt)
                history = format_prompt_from_variable(history, task)
                res = await llm_base.predict(
                    messages = history,
                    params = generation_params,
                    first_message = text if text is None else "alo",
                    start_message = task.get("start_message"),
                    session_id = task.get("session_id"),
                    language = task.get("language"),
                    **kwargs
                )
            else :
                history.append({
                    "role": "user",
                    "content": text,
                })
                res = await llm_base.predict(
                    messages = history,
                    params = generation_params,
                    start_message = task.get("start_message"),
                    session_id = task.get("session_id"),
                    **kwargs
                )
            # logging.info(f"======[PipelineTask] res: {res}")
            if not isinstance(res, dict):
                if format_output == "TEXT":
                    history.append({
                        "role": "assistant",
                        "content": self.res_error.get("answer"),
                    })
                else :
                    history.append({
                        "role": "assistant",
                        "content": json.dumps(self.res_error, ensure_ascii=False),
                    })
                return history_task, task_idx, self.res_error, None
            if format_output == "TEXT":
                history.append({
                    "role": "assistant",
                    "content": res.get("answer"),
                })
            else :
                history.append({
                    "role": "assistant",
                    "content": json.dumps(res, ensure_ascii=False),
                })
            history_task[task_idx] = history
            if res.get("status") == "END":
                task_idx += 1
                ## EXTRACTIION CONTEXT
                SYSTEM_EXTRACTION_VARIABLES = task_chain[task_idx-1].get("SYSTEM_EXTRACTION_VARIABLES")
                SYSTEM_CONVERSATION_HISTORY = get_system_conversation_history(history)
                context_variables = copy.deepcopy(task)
                context_variables["SYSTEM_EXTRACTION_VARIABLES"] = SYSTEM_EXTRACTION_VARIABLES
                context_variables["SYSTEM_CONVERSATION_HISTORY"] = SYSTEM_CONVERSATION_HISTORY
                if SYSTEM_EXTRACTION_VARIABLES not in ["", None]:
                    history_context_variable = [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT_EXTRACTIONS,
                        },
                        {
                            "role": "user",
                            "content": SYSTEM_CONVERSATION_HISTORY
                        }
                    ]
                    history_context_variable = format_prompt_from_variable(history_context_variable, context_variables)
                    res_context_variable = await llm_base.get_response(
                        messages = history_context_variable,
                        **generation_params,
                    )
                    res_context_variable = llm_base.parsing_json(res_context_variable)
                    if isinstance(res_context_variable, dict):
                        system_context_variables.update(res_context_variable)

                
                SYSTEM_PROMPT_GENERATION = task_chain[task_idx-1].get("SYSTEM_PROMPT_GENERATION")
                if SYSTEM_PROMPT_GENERATION not in ["", None]:
                    history_prompt_generation = [
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT_GENERATION,
                        }
                    ]
                    history_prompt_generation = format_prompt_from_variable(history_prompt_generation, system_context_variables)
                    res_context_generation = await llm_base.get_response(
                        messages = history_prompt_generation,
                        **generation_params,
                    )
                    res_context_generation = llm_base.parsing_json(res_context_generation)
                    logging.info(f"============res_context_generation: {res_context_generation}")
                    if isinstance(res_context_generation, dict):
                        system_context_variables.update(res_context_generation)
            
            for key in response.keys():
                if key == "correct_answer":
                    response[key] = response.get(key) if response.get(key) == "TRUE" else res.get(key)
                elif key == "answer":
                    if isinstance(res.get(key), list):
                        response[key].extend(res.get(key))
                    else :
                        response[key].append(res.get(key))
                else :
                    response[key] = res.get(key)
            # logging.info(f"[PipelineTask] task_idx: {task_idx} - status: {response.get('status')}")
            if response.get("status") == "END" and task_idx >= len(task_chain):
                break
            if response.get("status") != "END":
                break

        return history_task, task_idx, response, system_context_variables
    

    async def run_tools(
        self,
        input: Dict[str, str],
        tools: Dict[str, str],
        timeout: int = 5,
        **kwargs
    ) -> List[dict]:
        try:
            for tool in tools:
                logging.info(f"[PipelineTask] tool: {tool}")
                if not isinstance(tool, dict) or not isinstance(tool.get("tool_name"), str):
                    continue
                tool_object = TOOL_OBJECTS.get(tool.get("tool_name"))
                if tool_object is None:
                    continue
                response = await tool_object.process(
                    input = input,
                    tool = tool,
                    timeout = timeout,
                    **kwargs
                )
                logging.info(f"[PipelineTask] Tool response: {response}")
                if response.get("tool_status") in ["ERROR", "PASS"]:
                    continue
                return response
            return {
                "text": None,
                "tool_status": "PASS",
            }
        except Exception as e:
            logging.error(f"[PipelineTask] run_tools error: {e}")
            return {
                "text": None,
                "tool_status": "ERROR",
            }
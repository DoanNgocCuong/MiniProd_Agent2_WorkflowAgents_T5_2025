import copy, json, logging
import time, asyncio, uuid
from typing import List, Dict
from src.chatbot.prompt import SYSTEM_PROMPT, format_prompt_from_variable, get_system_conversation_history, SYSTEM_PROMPT_EXTRACTIONS, format_text_from_input_slots
from src.chatbot.llm_base import BaseLLM
from src.tools.tool_interface import ToolInterface
from src.tools.tool_config import TOOL_OBJECTS
from src.utils.utils import call_api_get_user_profile, callAPIPropertyMatching
from src.channel.mysql_bot import MYSQL_BOT


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class PipelineTask:

    
    def __init__(self, redis_client: object, rabbit_client: object):
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
        self.redis_client = redis_client
        self.rabbit_client = rabbit_client

    async def process(
        self, 
        text: str, 
        task_idx: int, 
        history_task: List[list], 
        task_chain: List[dict], 
        llm_base: BaseLLM, 
        generation_params: dict,
        bot_id: int = None,
        **kwargs
    ) -> List[dict]:
        response = {
            "status": None,
            "answer": [],
            "correct_answer": "NONE",
            "language": "vi",
            "sentence": None,
        }
        cur_status = kwargs.get("cur_status")
        format_output = kwargs.get("format_output")
        system_context_variables = kwargs.get("system_context_variables", {})
        if system_context_variables is None:
            system_context_variables = {}
        system_context_variables["MOOD"] = ""
        system_context_variables["IMAGE"] = ""
        system_context_variables["LANGUAGE"] = ""

        # Start Check Extract And Update User Profile
        conversation_id = kwargs.get("conversation_id")
        start_time = time.time()
        while time.time() - start_time < 5:
            if self.redis_client.get(f"{conversation_id}_USER_PROFILE") in ["END", None]:
                break
            await asyncio.sleep(0.1)
        ## END Check Extract And Update User Profile
            
        if cur_status == "INIT":
            user_profile = await call_api_get_user_profile(kwargs.get("conversation_id"))
            if user_profile and isinstance(user_profile, dict):
                system_context_variables.update(user_profile)

        if cur_status in ["END", "ACTION"]:
            user_profile = await call_api_get_user_profile(kwargs.get("conversation_id"))
            if user_profile and isinstance(user_profile, dict):
                system_context_variables.update(user_profile)
                
            task_idx += 1
            system_context_variables = await self.run_param_extractor(
                task_chain=task_chain,
                history=history_task[task_idx - 1],
                generation_params=generation_params,
                llm_base=llm_base,
                system_context_variables=system_context_variables,
                task_idx=task_idx - 1,
                bot_id=bot_id,
                conversation_id=kwargs.get("conversation_id"),
            )
        

        if task_idx >= len(task_chain):
            if cur_status in ["END", "ACTION"]:
                return history_task, task_idx, {"status": "END","answer": "ACTION",}, system_context_variables, cur_status  
            return history_task, task_idx, self.res_error, system_context_variables, cur_status
        if isinstance(kwargs.get("history"), list) and len(kwargs.get("history")) > 0:
            history_task[task_idx] = kwargs.get("history")
        if task_idx < len(task_chain):
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
                    task_name = "AGENT_PREDICTION",
                    bot_id = bot_id,
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
                    task_name = "AGENT_PREDICTION",
                    bot_id = bot_id,
                    **kwargs
                )
            
            ## FORMAT ANSWER
            variables_memory = copy.deepcopy(kwargs.get("input_slots", {}))
            if isinstance(variables_memory, dict) and isinstance(system_context_variables, dict):
                variables_memory.update(copy.deepcopy(system_context_variables))
            assistant_answer = format_text_from_input_slots(text=res.get("answer"), input_slots=variables_memory)
            res["answer"] = assistant_answer
            ## END FORMAT ANSWER

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
                return history_task, task_idx, self.res_error, system_context_variables, cur_status
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

            task_id = f"{kwargs.get('conversation_id')}_{str(uuid.uuid4())}"
            if kwargs.get("user_id") is not None:
                self.rabbit_client.send_task(
                    message = json.dumps({
                        "conversation_id": kwargs.get("conversation_id"),
                        "task_id": task_id,
                        "history": history,
                        "user_id": kwargs.get("user_id"),
                        "res": res,
                        "task_name": "PIKA_MEMORY",
                        "bot_id": bot_id,
                    }, ensure_ascii=False)
                )
                self.redis_client.set(
                    key = task_id,
                    value = "PROCESSING",
                    expire_time = 20,
                )

            history_task[task_idx] = history
            # if res.get("status") == "END":
            #     task_idx += 1
            
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
            cur_status = copy.deepcopy(response.get("status"))
            if response.get("status") == "END":
                if task_idx < len(task_chain) - 1:
                    response["status"] = "ACTION"
            
            if kwargs.get("cur_status") in ["INIT", "ACTION", "END"]:
                system_context_variables["MOOD"] = task_chain[task_idx].get("MOOD") if task_chain[task_idx].get("MOOD") else ""
                system_context_variables["IMAGE"] = task_chain[task_idx].get("IMAGE") if task_chain[task_idx].get("IMAGE") else ""
                if task_chain[task_idx].get("LANGUAGE") is not None:
                    system_context_variables["LANGUAGE"] = task_chain[task_idx].get("LANGUAGE")
                elif task_chain[task_idx].get("language") is not None:
                    system_context_variables["LANGUAGE"] = task_chain[task_idx].get("language")
                else :
                    system_context_variables["LANGUAGE"] = ""
            else :
                property_matching = await callAPIPropertyMatching(
                    conversation_id=kwargs.get("conversation_id"),
                    bot_id=bot_id,
                    messages=history,
                )
                if property_matching and isinstance(property_matching, dict):
                    system_context_variables["MOOD"] = property_matching.get("mood")
                    system_context_variables["IMAGE"] = property_matching.get("image")
                    system_context_variables["LANGUAGE"] = property_matching.get("language")
        
        ## WAIT FOR PIKA MEMORY
        while time.time() - start_time < 5:
            if self.redis_client.get(task_id) != "PROCESSING":
                break
            await asyncio.sleep(0.2)
        memory_answer = self.get_memory_answer(task_id)
        logging.info(f"==========[PipelineTask] - {task_id} - {kwargs.get('user_id')} - memory_answer: {memory_answer}")
        if memory_answer is not None:
            response["answer"] = memory_answer
        ## END WAIT FOR PIKA MEMORY

        return history_task, task_idx, response, system_context_variables, cur_status
    

    def get_memory_answer(self, task_id: str):
        try:
            memory_result = self.redis_client.get(task_id)
            if memory_result in [None, "NONE", "PROCESSING", "END"]:
                return None
            logging.info(f"==========[PipelineTask] - {task_id} - memory_result: {memory_result}")
            memory_result = json.loads(memory_result)
            if isinstance(memory_result, dict) and memory_result.get("status") == 200:
                return memory_result.get("result")
            return None
        except Exception as e:
            import traceback
            logging.error(f"[PipelineTask] get_memory_result error: {traceback.format_exc()}")
            return None
    

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
        
    async def run_param_extractor(self, task_chain, history, task_idx, llm_base, generation_params, system_context_variables, **kwargs):
        ## EXTRACTIION CONTEXT
        SYSTEM_EXTRACTION_VARIABLES = task_chain[task_idx].get("SYSTEM_EXTRACTION_VARIABLES")
        SYSTEM_CONVERSATION_HISTORY = get_system_conversation_history(history)
        task = copy.deepcopy(task_chain[task_idx])
        for key in system_context_variables:
            if system_context_variables.get(key) is not None:
                task[key] = copy.deepcopy(system_context_variables.get(key))
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
                params = generation_params,
                task_name="EXTRACTION",
                **kwargs,
            )
            res_context_variable = llm_base.parsing_json(res_context_variable)
            if isinstance(res_context_variable, dict):
                system_context_variables.update(res_context_variable)

        
        SYSTEM_PROMPT_GENERATION = task_chain[task_idx].get("SYSTEM_PROMPT_GENERATION")
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
                params = generation_params,
                task_name="GENERATION",
                **kwargs,
            )
            res_context_generation = llm_base.parsing_json(res_context_generation)
            # logging.info(f"============res_context_generation: {res_context_generation}")
            if isinstance(res_context_generation, dict):
                system_context_variables.update(res_context_generation)
        return system_context_variables
    

    def normalize_response_split(self, text: str, variables: dict):
        if isinstance(text, list) and isinstance(text[0], dict):
            return text
        return [
            {
                "text": ". ".join(text) if isinstance(text, list) else text,
                "mood":"" if not isinstance(variables, dict) else variables.get("MOOD"),
                "image":"" if not isinstance(variables, dict) else variables.get("IMAGE"),
                "video":"" if not isinstance(variables, dict) else variables.get("VIDEO"),
                "moods":[] if not isinstance(variables, dict) else variables.get("MOODS"),
                # "listening_animations":[] if not isinstance(variables, dict) else variables.get("LISTENING_ANIMATIONS"),
                # "language":"" if not isinstance(variables, dict) else variables.get("LANGUAGE"),
                "voice_speed":"" if not isinstance(variables, dict) else variables.get("VOICE_SPEED"),
                "text_viewer":"" if not isinstance(variables, dict) else variables.get("TEXT_VIEWER"),
                "volume": "" if not isinstance(variables, dict) else variables.get("VOLUME"),
                "audio": None,
                # "image_listening": "" if not isinstance(variables, dict) else variables.get("IMAGE_LISTENING"),
                # "mp3_listening": "" if not isinstance(variables, dict) else variables.get("MP3_LISTENING"),
                "model": "" if not isinstance(variables, dict) else variables.get("MODEL"),
            }
        ]
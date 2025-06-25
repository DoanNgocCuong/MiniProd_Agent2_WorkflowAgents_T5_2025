import logging, json, os, traceback
import mysql.connector
from typing import List, Dict
from .mysql_connector import MysqlConnector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class LLMBot:
    def __init__(
        self, 
        host: str, 
        username: str, 
        password: str, 
        database: str, 
        port: int,
        **kwargs
    ) -> None:
        
        self.connector = MysqlConnector()
        self.host = host
        self.username = username
        self.password = password
        self.database = database
        self.port = port
    
    
    def insert_bot(self, 
        name: str,
        description: str,
        scenario: List[dict],
        generation_params: dict,
        provider_name: str,
        system_prompt: str = None,
        system_extraction_variables: str = None,
        system_prompt_generation: str = None,
        system_extraction_profile: str = None,
        data_excel: List[dict] = None,
        **kwargs
    ) -> int:
        try :
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            query = """
                INSERT INTO llm_bot (name, description, scenario, generation_params, provider_name, create_at, update_at, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, data_excel) 
                VALUES (%s, %s, %s, %s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP(), %s, %s, %s, %s, %s)
            """
            values = (name, description, json.dumps(scenario, ensure_ascii=False), json.dumps(generation_params, ensure_ascii=False), provider_name, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, json.dumps(data_excel, ensure_ascii=False))
            cursor = connection.cursor()
            cursor.execute(query, values)

            # Lấy ID của bản ghi vừa được chèn
            bot_id = cursor.lastrowid

            connection.commit()
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Insertion Bot successful")
            return bot_id
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Insertion Bot Fail: {traceback.format_exc()}")
        return None
            
    
    def update_bot_from_id(self, 
        id: int,
        name: str = None,
        description: str = None,
        scenario: List[dict] = None,
        generation_params: dict = None,
        provider_name: str = None,
        system_prompt: str = None,
        system_extraction_variables: str = None,
        system_prompt_generation: str = None,
        system_extraction_profile: str = None,
        data_excel: List[dict] = None,
        **kwargs
    ) -> None:
        try :
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            query = """
                UPDATE llm_bot
                SET name = %s, description = %s, scenario = %s, generation_params = %s, provider_name = %s, update_at = UNIX_TIMESTAMP(), system_prompt = %s, system_extraction_variables = %s, system_prompt_generation = %s, system_extraction_profile = %s, data_excel = %s 
                WHERE id = %s
            """
            values = (name, description, json.dumps(scenario, ensure_ascii=False), json.dumps(generation_params, ensure_ascii=False), provider_name, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, json.dumps(data_excel, ensure_ascii=False), id)

            cursor = connection.cursor()
            cursor.execute(query, values)
            connection.commit()
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Update Bot successful")
            return True
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Update Bot Fail: {traceback.format_exc()}")
        return False
    

    def get_bot_from_id(self, id: int) -> Dict:
        try :
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            query = """
                SELECT id, name, description, scenario, generation_params, provider_name, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, data_excel FROM llm_bot WHERE id = %s
            """
            values = (id, )
            cursor = connection.cursor()
            cursor.execute(query, values)
            result = {}
            bot_config = cursor.fetchall()
            if bot_config:
                for id, name, description, scenario, generation_params, provider_name, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, data_excel in bot_config:
                    result = {
                        "id": id,
                        "name": name,
                        "description": description,
                        "scenario": json.loads(scenario) if scenario else [],
                        "generation_params": json.loads(generation_params) if generation_params else {},
                        "provider_name": provider_name,
                        "system_prompt": system_prompt,
                        "system_extraction_variables": system_extraction_variables,
                        "system_prompt_generation": system_prompt_generation,
                        "system_extraction_profile": system_extraction_profile,
                        "data_excel": json.loads(data_excel) if data_excel else [],
                    }
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Get Bot successful")
            return result
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Get Bot Fail: {traceback.format_exc()}")
        return {}
    

    def get_all_bot_config(self) -> List[Dict]:
        try :
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            query = """
                SELECT id, name, description, scenario, generation_params, provider_name, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, data_excel FROM llm_bot
            """
            cursor = connection.cursor()
            cursor.execute(query)
            bot_config = cursor.fetchall()
            result = []
            if bot_config:
                for id, name, description, scenario, generation_params, provider_name, system_prompt, system_extraction_variables, system_prompt_generation, system_extraction_profile, data_excel in bot_config:
                    result.append({
                        "id": id,
                        "name": name,
                        "description": description,
                        "task_chain": json.loads(scenario) if scenario else [],
                        "generation_params": json.loads(generation_params) if generation_params else {},
                        "provider_name": provider_name,
                        "system_prompt": system_prompt,
                        "system_extraction_variables": system_extraction_variables,
                        "system_prompt_generation": system_prompt_generation,
                        "system_extraction_profile": system_extraction_profile,
                        "data_excel": json.loads(data_excel) if data_excel else [],
                    })
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Get All Bot successful")
            return result
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Get All Bot Fail: {traceback.format_exc()}")
        return []

    
    def insert_llm_history(self, conversation_id, input_text, output_text, process_time, bot_id):
        try:
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            cursor = connection.cursor()
            insert_query = """
            INSERT INTO llm_history (conversation_id, input, output, process_time, create_at, bot_id)
            VALUES (%s, %s, %s, %s, UNIX_TIMESTAMP(), %s)
            """
            cursor.execute(insert_query, (conversation_id, input_text, output_text, process_time, bot_id))
            connection.commit()
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Insert LLM History successful")
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Insert LLM History Fail: {traceback.format_exc()}")

    
    def get_output_from_conversation_id(self, conversation_id: str, **kwargs) -> str:
        try:
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            query = """
                SELECT input, output FROM llm_history WHERE conversation_id = %s
            """
            cursor = connection.cursor()
            cursor.execute(query, (conversation_id,))
            result = cursor.fetchall()
            outputs = []
            if result:
                for text, out in result:
                    out = self.parsing_json(out)
                    if isinstance(out, dict):
                        outputs.append({
                            "user": text,
                            "assistant": "\n".join(out.get("text")) if isinstance(out.get("text"), list) else out.get("text")
                        })
            cursor.close()
            connection.close()
            return outputs
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Get Output from Conversation ID Fail: {traceback.format_exc()}")
            return None
        

    def parsing_json(self, json_str):
        try:
            return json.loads(json_str)
        except Exception as e:
            return json_str

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
                INSERT INTO lesson (name, description, scenario, create_at, update_at)
                VALUES (%s, %s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())
            """
            values = (name, description, json.dumps(scenario))
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
                UPDATE lesson
                SET scenario = %s, name = %s, description = %s, update_at = UNIX_TIMESTAMP() 
                WHERE id = %s
            """
            values = (json.dumps(scenario, ensure_ascii=False), name, description, id)

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
                SELECT id, name, description, scenario FROM lesson WHERE id = %s
            """
            values = (id, )
            cursor = connection.cursor()
            cursor.execute(query, values)
            result = {}
            bot_config = cursor.fetchall()
            if bot_config:
                for id, name, description, scenario in bot_config:
                    result = {
                        "id": id,
                        "name": name,
                        "description": description,
                        "scenario": json.loads(scenario) if scenario else [],
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
                SELECT id, name, description, scenario FROM lesson
            """
            cursor = connection.cursor()
            cursor.execute(query)
            bot_config = cursor.fetchall()
            result = []
            if bot_config:
                for id, name, description, scenario in bot_config:
                    result.append({
                        "id": id,
                        "name": name,
                        "description": description,
                        "scenario": json.loads(scenario) if scenario else [],
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
            INSERT INTO conversation_logging_lesson (conversation_id, input, output, process_time, create_at, bot_id)
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
                SELECT input, output FROM conversation_logging_lesson WHERE conversation_id = %s
            """
            cursor = connection.cursor()
            cursor.execute(query, (conversation_id,))
            result = cursor.fetchall()
            outputs = []
            if result:
                for text, out in result:
                    out = self.parsing_json(out)
                    if isinstance(out, dict):
                        assistant_text = None
                        if isinstance(out.get("text"), list):
                            assistant_text = "\n".join([item.get("text") if isinstance(item, dict) else item for item in out.get("text")])
                        else:
                            assistant_text = out.get("text")
                        outputs.append({
                            "user": text,
                            "assistant": assistant_text
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

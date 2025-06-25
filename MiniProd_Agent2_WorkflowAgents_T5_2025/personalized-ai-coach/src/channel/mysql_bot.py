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
        self.create_db()
    
    
    def create_db(self) -> None:
        try:
            connection = self.connector.get_connection(
                self.host, 
                self.username, 
                self.password, 
                self.database, 
                self.port
            )
            cursor = connection.cursor()

            # Create llm_bot table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_bot (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci NOT NULL,
                description TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                task_chain JSON,
                generation_params JSON,
                provider_name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                system_prompt LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                format_output LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                create_at BIGINT,
                update_at BIGINT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci;
            """)

            # Create llm_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                conversation_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci NOT NULL,
                input LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                output LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                process_time FLOAT,
                create_at BIGINT,
                bot_id INT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci;
            """)

            # Create conversation_logging table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_logging (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bot_id INT,
                conversation_id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci NOT NULL,
                task_name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                input LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                output LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                process_time FLOAT,
                provider_name VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci,
                create_at BIGINT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_vietnamese_ci;
            """)

            connection.commit()
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Database tables created successfully")
        except Exception as e:
            logging.error(f"[ERROR][MYSQL] Failed to create database tables: {traceback.format_exc()}")
    
    
    def insert_bot(self, 
        name: str,
        description: str,
        task_chain: List[dict],
        generation_params: dict,
        provider_name: str,
        system_prompt: str = None,
        format_output: str = None,
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
                INSERT INTO llm_bot (name, description, task_chain, generation_params, provider_name, create_at, update_at, system_prompt, format_output)
                VALUES (%s, %s, %s, %s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP(), %s, %s)
            """
            values = (name, description, json.dumps(task_chain), json.dumps(generation_params), provider_name, system_prompt, format_output)
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
        task_chain: List[dict],
        generation_params: dict,
        provider_name: str,
        system_prompt: str = None,
        format_output: str = None,
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
                SET task_chain = %s, generation_params = %s, provider_name = %s, update_at = UNIX_TIMESTAMP(), system_prompt = %s, format_output = %s 
                WHERE id = %s
            """
            values = (json.dumps(task_chain, ensure_ascii=False), json.dumps(generation_params, ensure_ascii=False), provider_name, system_prompt, format_output, id)

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
                SELECT id, name, description, task_chain, generation_params, provider_name, system_prompt, format_output FROM llm_bot WHERE id = %s
            """
            values = (id, )
            cursor = connection.cursor()
            cursor.execute(query, values)
            result = {}
            bot_config = cursor.fetchall()
            if bot_config:
                for id, name, description, task_chain, generation_params, provider_name, system_prompt, format_output in bot_config:
                    result = {
                        "id": id,
                        "name": name,
                        "description": description,
                        "task_chain": json.loads(task_chain) if task_chain else [],
                        "generation_params": json.loads(generation_params) if generation_params else {},
                        "provider_name": provider_name,
                        "system_prompt": system_prompt,
                        "format_output": format_output
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
                SELECT id, name, description, task_chain, generation_params, provider_name, system_prompt, format_output FROM llm_bot
            """
            cursor = connection.cursor()
            cursor.execute(query)
            bot_config = cursor.fetchall()
            result = []
            if bot_config:
                for id, name, description, task_chain, generation_params, provider_name, system_prompt, format_output in bot_config:
                    result.append({
                        "id": id,
                        "name": name,
                        "description": description,
                        "task_chain": json.loads(task_chain) if task_chain else [],
                        "generation_params": json.loads(generation_params) if generation_params else {},
                        "provider_name": provider_name,
                        "system_prompt": system_prompt,
                        "format_output": format_output
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

    def insert_conversation_logging(self, 
        bot_id: int,
        conversation_id: str,
        input_text: str,
        output_text: str,
        process_time: float,
        provider_name: str,
        task_name: str = None,
        **kwargs
    ) -> bool:
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
            INSERT INTO conversation_logging (bot_id, conversation_id, task_name, input, output, process_time, provider_name, create_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, UNIX_TIMESTAMP())
            """
            cursor.execute(insert_query, (bot_id, conversation_id, task_name, input_text, output_text, process_time, provider_name))
            connection.commit()
            cursor.close()
            connection.close()
            logging.info("[MYSQL] Insert Conversation Logging successful")
            return True
        except Exception as e:
            logging.info(f"[ERROR][MYSQL] Insert Conversation Logging Fail: {traceback.format_exc()}")
            return False


MYSQL_BOT = LLMBot(
    host=os.getenv("MYSQL_HOST"),
    username=os.getenv("MYSQL_USERNAME"),
    password=os.getenv("MYSQL_ROOT_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    port=os.getenv("MYSQL_PORT")
)
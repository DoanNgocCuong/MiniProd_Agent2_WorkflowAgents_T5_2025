import sys
import pika, json
import ssl, logging, traceback
import requests
import json, time, asyncio
from src.tools.tool_interface import ToolInterface
from src.channel.mysql_bot import MYSQL_BOT

logging.getLogger("pika").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class RabbitMQConsumer:
    def __init__(self, host: str, port: int, username: str, password: str, exchange: str,
        queue_name: str, rabbitmq_ssl: bool = False, rabbitmq_heartbeat: int = 30, 
        mysql_client: object = None, redis_client: object = None, graph_model: object = None, **kwargs):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange = exchange
        self.queue_name = queue_name
        self.rabbitmq_ssl = rabbitmq_ssl
        self.rabbitmq_heartbeat = rabbitmq_heartbeat
        self.mysql_client = mysql_client
        self.redis_client = redis_client
        self.graph = graph_model
        self.tool_interface = ToolInterface()
        self.function_callback = {
            "USER_PROFILE": self.call_profile_extraction,
            "CHECK_CALL_TOOL": self.call_check_call_tool,
            "PRONUNCIATION_CHECKER_TOOL": self.call_pronunciation_checker_tool,
            "GRAMMAR_CHECKER_TOOL": self.call_grammar_checker_tool,
            "PIKA_MEMORY": self.call_pika_memory,
        }
        self.loop = asyncio.get_event_loop()

    def on_message_callback(self, ch, method, properties, body):
        body=body.decode("utf-8")
        status = self.process_function_callback(data=body)
        if status == True:
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else :
            logging.info("[Rabbitmq] Message [x] Reject==: {}".format(body))
            # ch.basic_reject(delivery_tag = method.delivery_tag, requeue=True)

    def running_consumer(self):
        logging.info("[Rabbitmq] Start Working Consumer")
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=pika.PlainCredentials(self.username, self.password),
            ssl_options=pika.SSLOptions(ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)) if self.rabbitmq_ssl else None,
            heartbeat=self.rabbitmq_heartbeat)
        )
        channel = connection.channel()
        
        # Declare the exchange
        channel.exchange_declare(exchange=self.exchange, exchange_type='direct', durable=True)

        # Declare the queue (ensure the queue is bound to the exchange)
        channel.queue_declare(queue=self.queue_name, durable=True)

        # Bind the queue to the exchange
        channel.queue_bind(exchange=self.exchange, queue=self.queue_name, routing_key=self.queue_name)
        
        channel.basic_qos(prefetch_count=1)
        
        channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_message_callback)
        logging.info(f"[Rabbitmq] Waiting Message From Queue {self.queue_name}")
        channel.start_consuming()
        
    
    def process_function_callback(self, data: str):
        # tool = data.get("tool")
        # task_id = data.get("task_id")
        # logging.info(f"[Rabbitmq] Processing data {data}")
        try :
            data = json.loads(data)
            task_name = data.get("task_name")
            self.loop.run_until_complete(self.function_callback[task_name](**data))
            return True
        except :
            logging.info(f"[RabbitMQ Consummer] Error process_function_callback: {traceback.format_exc()}")
            return True
    

    async def call_profile_extraction(self, 
        conversation_id = None, 
        messages = None, 
        url = None, 
        task_name = None,
        **kwargs):
        start_time = time.time()
        try :
            res = await self.tool_interface.call_profile_extraction(
                conversation_id=conversation_id,
                messages=messages,
                url=url,
            )
            task_id = kwargs.get("task_id")
            if not task_id:
                task_id = conversation_id + "_USER_PROFILE"
            self.redis_client.set(
                key = task_id,
                value = "END",
                expire_time = 30,
            )
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=conversation_id,
                input_text=json.dumps(messages, ensure_ascii=False),
                output_text=json.dumps(res, ensure_ascii=False) if isinstance(res, dict) else res,
                process_time=time.time() - start_time,
                provider_name="",
                task_name=task_name,
            )
            return True
        except :
            logging.info(f"[RabbitMQ Consummer][call_profile_extraction] Error: {traceback.format_exc()}")
            return False

    async def call_check_call_tool(self, 
        task_name = None, 
        conversation_id = None, 
        history = None, 
        message = None, 
        task_id = None, 
        audio_url = None, 
        value = None, 
        tool = {},
        **kwargs):
        try :
            start_time = time.time()
            if isinstance(history, list) and len(history) > 0 and isinstance(message, str):
                history.append({
                    "role": "user",
                    "content": message
                })
            res = await self.tool_interface.check_call_tool(
                conversation_id=conversation_id,
                messages=history,
            )
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=conversation_id,
                input_text=json.dumps(history, ensure_ascii=False),
                output_text=json.dumps(res, ensure_ascii=False) if isinstance(res, dict) else res,
                process_time=time.time() - start_time,
                provider_name="",
                task_name=task_name,
            )
            self.redis_client.set(
                key = task_id,
                value = json.dumps({
                    "status": 200,
                    "result": res
                }, ensure_ascii=False),
                expire_time = 10,
            )
        except :
            logging.info(f"[RabbitMQ Consummer][call_check_call_tool] Error: {traceback.format_exc()}")
            self.redis_client.set(
                key = task_id,
                value = json.dumps({
                    "status": 500,
                    "result": False
                }, ensure_ascii=False),
                expire_time = 10,
            )
    
    async def call_pronunciation_checker_tool(self, 
        task_name = None, 
        conversation_id = None, 
        history = None, 
        message = None, 
        task_id = None, 
        audio_url = None, 
        value = None, 
        tool = {},
        **kwargs):
        try :
            start_time = time.time()
            question = None
            if isinstance(tool, dict):
                text_refs = tool.get("text_refs") if tool.get("text_refs") is not None else message
            res = await self.tool_interface.process(
                conversation_id=task_id,
                tool_name=task_name,
                audio_url=audio_url,
                message=message,
                text_refs=text_refs,
                question=question,
            )
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=conversation_id,
                input_text=json.dumps(history, ensure_ascii=False),
                output_text=json.dumps(res, ensure_ascii=False) if isinstance(res, dict) else res,
                process_time=time.time() - start_time,
                provider_name="",
                task_name=task_name,
            )
            logging.info(f"[Rabbitmq Consummer][call_pronunciation_checker_tool] ====================res: {res}")
            if isinstance(res, dict):
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({
                        "status": 200,
                        "result": {
                            "TOOL_NAME": task_name,
                            "TOOL_CONVERSATION_ID": conversation_id,
                            "TOOL_RESULT": res,
                            "TOOL_SETTING": tool,
                        }
                    }, ensure_ascii=False),
                    expire_time = 10,
                )
        except :
            logging.info(f"[RabbitMQ Consummer][call_pronunciation_checker_tool] Error: {traceback.format_exc()}")
            self.redis_client.set(
                key = task_id,
                value = json.dumps({
                    "status": 500,
                    "result": None
                }, ensure_ascii=False),
                expire_time = 10,
            )
            
    async def call_grammar_checker_tool(self, 
        task_name = None, 
        conversation_id = None, 
        history = None, 
        message = None, 
        task_id = None, 
        audio_url = None, 
        tool = {},
        **kwargs):
        try :
            start_time = time.time()
            if isinstance(tool, dict):
                question = []
                for item in history:
                    if item.get("role") == "user":
                        question.append("User: " + item.get("content"))
                    elif item.get("role") == "assistant":
                        question.append("Assistant: " + item.get("content"))
                question = "\n".join(question)
                text_refs = None
                res = await self.tool_interface.process(
                    conversation_id=task_id,
                    tool_name=task_name,
                    audio_url=audio_url,
                    message=message,
                    text_refs=text_refs,
                    question=question,
                )
                MYSQL_BOT.insert_conversation_logging(
                    bot_id=kwargs.get("bot_id"),
                    conversation_id=conversation_id,
                    input_text=json.dumps(history, ensure_ascii=False),
                    output_text=json.dumps(res, ensure_ascii=False) if isinstance(res, dict) else res,
                    process_time=time.time() - start_time,
                    provider_name="",
                    task_name=task_name,
                )
                logging.info(f"[Rabbitmq Consummer][call_grammar_checker_tool] ====================res: {res}")
                if isinstance(res, dict):
                    self.redis_client.set(
                        key = task_id,
                        value = json.dumps({
                            "status": 200,
                            "result": {
                                "TOOL_NAME": task_name,
                                "TOOL_CONVERSATION_ID": conversation_id,
                                "TOOL_RESULT": res,
                                "TOOL_SETTING": tool,
                            }
                        }, ensure_ascii=False),
                        expire_time = 10,
                    )
        except :
            logging.info(f"[RabbitMQ Consummer][call_grammar_checker_tool] Error: {traceback.format_exc()}")
            self.redis_client.set(
                key = task_id,
                value = json.dumps({
                    "status": 500,
                    "result": None
                }, ensure_ascii=False),
                expire_time = 10,
            )
            return True

    async def call_pika_memory(self, 
        conversation_id = None, 
        history = None, 
        res = None, 
        task_id = None, 
        **kwargs):
        try :
            start_time = time.time()
            ## CALL API PIKA MEMORY
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "conversation_id": conversation_id,
                "metadata": {
                    "conversation_id": conversation_id,
                    "query": history[-1].get("content"),
                    "user_id": kwargs.get("user_id"),
                    "limit": 1,
                }
            }
            fact_value = None
            response_search = None
            if kwargs.get("user_id") is not None:
                response_search  = await self.tool_interface.aync_call_api(
                    url=f"{str(self.tool_interface.tool_executor_url)}/mem0Search",
                    headers=headers,
                    payload=payload,
                    timeout=5,
                    method="POST",
                    task_name="MEM0SEARCH",
                )
                # logging.info(f"============[Rabbitmq Consummer][call_pika_memory] response_search: {response_search}")
                if isinstance(response_search, dict) and response_search.get("status") == 0:
                    fact_value = response_search.get("result")[0].get("fact_value")
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=conversation_id,
                input_text=json.dumps(payload, ensure_ascii=False),
                output_text=json.dumps(response_search, ensure_ascii=False) if isinstance(response_search, dict) else response_search,
                process_time=time.time() - start_time,
                provider_name="",
                task_name="MEM0SEARCH",
            )


            memory_answer = None
            response_generation = None
            if fact_value:
                ## CALL API PIKA GENERATION ANSWER
                headers = {
                    "Content-Type": "application/json"
                }
                payload = {
                    "conversation_id": conversation_id,
                    "messages": history,
                    "metadata": {
                        "ASSISTANT_ANSWER": history[-1].get("content"),
                        "USER_FACT": fact_value,
                    },
                }
                response_generation = await self.tool_interface.aync_call_api(
                    url=f"{str(self.tool_interface.tool_executor_url)}/mem0Generation",
                    headers=headers,
                    payload=payload,
                    timeout=5,
                    method="POST",
                    task_name="MEM0GENERATION",
                )
                # logging.info(f"============[Rabbitmq Consummer][call_pika_memory] response_generation: {response_generation}")
                if isinstance(response_generation, dict) and response_generation.get("status") == 0:
                    memory_answer = response_generation.get("result")
                
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=conversation_id,
                input_text=json.dumps(payload, ensure_ascii=False),
                output_text=json.dumps(response_generation, ensure_ascii=False) if isinstance(response_generation, dict) else response_generation,
                process_time=time.time() - start_time,
                provider_name="",
                task_name="MEM0GENERATION",
            )
            if memory_answer:
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({
                        "status": 200,
                        "result": memory_answer,
                    }, ensure_ascii=False),
                    expire_time = 5 * 60,
                )
            else :
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({
                        "status": 404,
                        "result": None
                    }, ensure_ascii=False),
                    expire_time = 5 * 60,
                )
        except :
            logging.info(f"[RabbitMQ Consummer][call_pika_memory] Error: {traceback.format_exc()}")
            self.redis_client.set(
                key = task_id,
                value = json.dumps({
                    "status": 500,
                    "result": None
                }, ensure_ascii=False),
                expire_time = 5 * 60,
            )
            MYSQL_BOT.insert_conversation_logging(
                bot_id=kwargs.get("bot_id"),
                conversation_id=conversation_id,
                input_text=json.dumps(payload, ensure_ascii=False),
                output_text=str(traceback.format_exc()),
                process_time=time.time() - start_time,
                provider_name="",
                task_name="MEM0SEARCH_GENERATION",
            )
            return False
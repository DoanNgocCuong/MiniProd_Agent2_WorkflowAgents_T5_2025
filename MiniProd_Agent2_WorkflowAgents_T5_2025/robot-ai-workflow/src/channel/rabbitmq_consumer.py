import sys, os
import pika, json
import ssl, logging, traceback
import requests
import json, time, asyncio
from src.tools.tool_interface import ToolInterface


logging.getLogger("pika").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

URL_PIKA_MEMORY = os.getenv("URL_PIKA_MEMORY") if os.getenv("URL_PIKA_MEMORY") is not None else ""

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
        self.functions = {
            "USER_PROFILE": self.process_function_user_profile,
            "PIKA_MEMORY": self.process_function_pika_memory,
            "CALLBACK_TOOL": self.process_function_callback_tool,
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
        logging.info(f"[Rabbitmq] Processing data {data}")
        try :
            data = json.loads(data)
            task_name = data.get("task_name")
            if not task_name:
                task_name = "CALLBACK_TOOL"
            self.loop.run_until_complete(self.functions.get(task_name)(data))
            return True
        except :
            logging.info(f"[RabbitMQ Consummer] Error process_function_callback: {traceback.format_exc()}")
            return True
        return True


    async def process_function_user_profile(self, data: dict):
        res = await self.tool_interface.call_profile_extraction(
            conversation_id=data.get("conversation_id"),
            messages=data.get("messages"),
            url=data.get("url"),
        )
        task_id = data.get("task_id")
        if not task_id:
            task_id = data.get("conversation_id") + "_USER_PROFILE"
        self.redis_client.set(
            key = task_id,
            value = "END",
            expire_time = 30,
        )
        return True

    
    async def process_function_callback_tool(self, data: dict):
        conversation_id = data.get("conversation_id")
        task_id = data.get("task_id")
        message = data.get("message")
        tool = data.get("tool")
        metadata = {}
        tool_conversation_id = str(conversation_id) + "-TOOL-" + str(int(time.time() * 1000))
        if isinstance(tool, dict) and isinstance(tool.get('value'), dict):
            text_refs = tool.get("value").get("text_refs")
            question = tool.get("value").get("question")
            key = tool.get("key")
            if key == "PRONUNCIATION_CHECKER_TOOL" and not text_refs:
                text_refs = message
            metadata["threshold"] = tool.get("value").get("threshold")
            res = await self.tool_interface.process(
                conversation_id=task_id,    
                tool_name=key,
                audio_url=data.get("audio_url"),
                message=message,
                text_refs=text_refs,
                question=question,
                metadata=metadata,
            )
            logging.info(f"[Rabbitmq Consummer] ====================res: {res}")
            if isinstance(res, dict):
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({
                        "TOOL_NAME": key,
                        "TOOL_CONVERSATION_ID": tool_conversation_id,
                        "TOOL_RESULT": res,
                        "TOOL_SETTING": tool.get("value"),
                    }, ensure_ascii=False),
                    expire_time = 10,
                )
            else :
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({}),
                    expire_time = 10,
                )
        else :
            self.redis_client.set(
                key = task_id,
                value = json.dumps({}),
                expire_time = 10,
            )

    
    async def process_function_pika_memory(self, data: dict):
        try :
            start_time = time.time()
            task_id = data.get("task_id")
            memory_answer = None
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "conversation_id": data.get("conversation_id"),
                "messages": data.get("history"),
                "metadata": {
                    "ASSISTANT_ANSWER": data.get("history")[-1].get("content"),
                    "user_id": data.get("user_id"),
                    "limit": 3,
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
            if isinstance(response_generation, dict) and response_generation.get("status") == 0:
                memory_answer = response_generation.get("result")
            logging.info(f"============[Rabbitmq Consummer][call_pika_memory] - {task_id} - memory_answer: {memory_answer}")
            if memory_answer:
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({
                        "status": 200,
                        "result": response_generation.get("result"),
                    }, ensure_ascii=False),
                    expire_time = 5 * 60,
                )
            else :
                self.redis_client.set(
                    key = task_id,
                    value = json.dumps({
                        "status": 404,
                        "result": None,
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
            return False
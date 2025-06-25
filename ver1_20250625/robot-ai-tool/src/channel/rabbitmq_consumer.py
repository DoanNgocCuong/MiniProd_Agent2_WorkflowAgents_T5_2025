import sys
import pika, json
import ssl, logging, traceback
import requests, os, yaml
import json, time, asyncio
import requests
import json
from src.llm_base import LLMBase
from src.prompts import SYSTEM_PROMPT_AGENT_CHAT
from typing import List
from src.tool_executor import ToolExecutor


logging.getLogger("pika").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

PATH_FILE_CONFIG = os.getenv("PATH_FILE_CONFIG") if os.getenv("PATH_FILE_CONFIG") is not None else "config.yml"
with open(PATH_FILE_CONFIG, "r") as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)
    PROVIDER_MODELS = CONFIG.get("PROVIDER_MODELS")
    LLM_MANAGER = {}
    for provider_name, value in PROVIDER_MODELS.items():
        openai_setting = value.get("openai_setting")
        openai_setting["api_key"] = os.getenv(openai_setting.get("api_key"))
        LLM_MANAGER[provider_name] = LLMBase(
            openai_setting = openai_setting,
            provider_name = provider_name,
        )
    PROVIDER_NAME = os.getenv("PROVIDER_NAME")
    LOOP_ASYNCIO = asyncio.get_event_loop()
    TOOL_EXECUTOR = ToolExecutor(
        provider_models = PROVIDER_MODELS,
        tool_config = CONFIG.get("TOOL_CONFIG"),
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
            conversation_id = data.get("conversation_id")
            task_name = data.get("task_name")
            if task_name == "PROPERITY_MATCHING":
                self.function_callback_properity_matching(data)
                return True

            self.redis_client.set(
                key = conversation_id,
                value = "PROCESSING",
            )

            input_slots = data.get("input_slots")
            bot_type = data.get("bot_type")
            bot_id = data.get("bot_id")
            url = None
            if bot_type == "Agent":
                url = os.getenv("URL_AGENT")
            if bot_type == "Workflow":
                url = os.getenv("URL_WORKFLOW")
            if bot_type == "Lesson":
                url = os.getenv("URL_LESSON")
            logging.info(f"[RabbitMQ Consummer] url: {url}")
            if not url:
                self.redis_client.set(
                    key = conversation_id,
                    value = "ERROR",
                )
                return True

            # Call API Init Conversation
            init_res = self.callAPIInitConversation(
                url = f"{url}/bot/initConversation",
                conversation_id = conversation_id,
                bot_id = bot_id,
                input_slots = input_slots,
            )
            if not isinstance(init_res, dict) or init_res.get("status") != 0:
                self.redis_client.set(
                    key = conversation_id,
                    value = "ERROR",
                )
                return True
            
            history = []
            for i in range(50):
                if i == 0:
                    webhook_res = self.callAPIWebhook(
                        url = f"{url}/bot/webhook",
                        conversation_id = conversation_id,
                        first_message = "alo",
                        message="alo"
                    )
                    message = None
                else :
                    message = self.get_next_message(
                        history = history,
                        status = webhook_res.get("status")
                    )
                    if message is None:
                        break
                    webhook_res = self.callAPIWebhook(
                        url = f"{url}/bot/webhook",
                        conversation_id = conversation_id,
                        message=message
                    )
                if isinstance(webhook_res, dict) and webhook_res.get("status") in ["END", "ERROR"]:
                    logging.info(f"============================================END==========")
                    break
                if message:
                    history.append({
                        "role": "user",
                        "content": message,
                    })
                anwser = webhook_res.get("text")
                anwser = ". ".join(anwser) if isinstance(anwser, list) else anwser
                history.append({
                    "role": "assistant",
                    "content": anwser,
                })

            self.redis_client.set(
                key = conversation_id,
                value = "END",
            )
        except :
            logging.info(f"[RabbitMQ Consummer] Error process_function_callback: {traceback.format_exc()}")
            return True
        return True

    def callAPIInitConversation(self, url: str, conversation_id: str, bot_id: int, input_slots: dict = None):
        try:
            payload = json.dumps({
                "conversation_id": conversation_id,
                "input_slots": input_slots,
                "bot_id": bot_id
            })
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.request("POST", url, headers=headers, data=payload, timeout=15)
            logging.info(f"[RabbitMQ Consummer] callAPIInitConversation: {url} - {payload} - {response.text}")
            res = response.json()
            return res
        except Exception as e:
            logging.error(f"[RabbitMQ Consummer] Error callAPIInitConversation: {traceback.format_exc()}")
            return None
        
        
    def callAPIWebhook(self, url: str, conversation_id: str, first_message: str = None, message: str = None):
        try:
            if first_message is not None:
                payload = json.dumps({
                    "conversation_id": conversation_id,
                    "message": first_message,
                    "first_message": message,
                })
            else :
                payload = json.dumps({
                    "conversation_id": conversation_id,
                    "message": message,
                })
            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload, timeout=15)
            logging.info(f"[RabbitMQ Consummer] callAPIWebhook: {url} - {payload} - {response.text}")
            res = response.json()
            return res
        except Exception as e:
            logging.error(f"[RabbitMQ Consummer] Error callAPIWebhook: {traceback.format_exc()}")
            return None
    
    def get_next_message(self, history: list, status: str):
        try:
            if status == "ACTION":
                return "ACTION"
            text = self.get_message_user_from_history(history)
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT_AGENT_CHAT,
                },
                {
                    "role": "user",
                    "content": text,
                }
            ]
            for _ in range(2):
                generation_params = PROVIDER_MODELS.get(PROVIDER_NAME).get("generation_params")
                response = LOOP_ASYNCIO.run_until_complete(LLM_MANAGER.get(PROVIDER_NAME).predict(
                    messages = messages,
                    params = generation_params
                ))
                if response:
                    return response
            return None
        except Exception as e:
            logging.error(f"[RabbitMQ Consummer] Error get_next_message: {traceback.format_exc()}")
            return None
        
    def get_message_user_from_history(self, history: List[dict]) -> str:
        try:
            text = []
            for message in history:
                if message.get("role") == "user":
                    text.append(f"Student: {message.get('content')}")
                if message.get("role") == "assistant":
                    text.append(f"Teacher: {message.get('content')}")
            return "\n".join(text)
        except Exception as e:
            logging.error(f"[RabbitMQ Consummer] Error get_message_user_from_history: {traceback.format_exc()}")
            return None
        
    def function_callback_properity_matching(self, data: dict):
        try:
            job_name = data.get("job_name")
            if job_name == "IMAGE_MATCHING":
                image = LOOP_ASYNCIO.run_until_complete(TOOL_EXECUTOR.image_matching.process(
                    bot_id = data.get("bot_id"),
                    conversation_history = data.get("messages"),
                ))
                logging.info(f"===============[RabbitMQ Consummer] image: {image}")
                if not image:
                    image = "NOT_FOUND"
                self.redis_client.set(
                    key = data.get("task_id"),
                    value = image,
                    expire_time = 5 * 60,
                )
                return True
            if job_name == "LANGUAGE_MATCHING":
                language = LOOP_ASYNCIO.run_until_complete(TOOL_EXECUTOR.language_matching.process(
                    bot_id = data.get("bot_id"),
                    conversation_history = data.get("messages"),
                ))
                logging.info(f"===============[RabbitMQ Consummer] language: {language}")
                if not language:
                    language = "NOT_FOUND"
                self.redis_client.set(
                    key = data.get("task_id"),
                    value = language,
                    expire_time = 5 * 60,
                )
                return True
            if job_name == "MOOD_MATCHING":
                mood = LOOP_ASYNCIO.run_until_complete(TOOL_EXECUTOR.mood_matching.process(
                    bot_id = data.get("bot_id"),
                    conversation_history = data.get("messages"),
                ))
                logging.info(f"===============[RabbitMQ Consummer] mood: {mood}")
                if not mood:
                    mood = "NOT_FOUND"
                self.redis_client.set(
                    key = data.get("task_id"),
                    value = mood,
                    expire_time = 5 * 60,
                )
                return True
        except Exception as e:
            logging.error(f"[RabbitMQ Consummer] Error function_callback_properity_matching: {traceback.format_exc()}")
            return None

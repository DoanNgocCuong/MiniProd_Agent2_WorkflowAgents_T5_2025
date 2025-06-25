import sys
import pika, json
import ssl, logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class RabbitMQClient:
    def __init__(self, host: str, port: int, username: str, password: str, exchange: str,
                 queue_name: str, rabbitmq_ssl: bool = False, rabbitmq_heartbeat: int = 30,
                 exchange_dead_letter = None, routing_key_dead_letter = None, **kwargs):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.exchange = exchange
        self.queue_name = queue_name
        self.rabbitmq_ssl = rabbitmq_ssl
        self.rabbitmq_heartbeat = rabbitmq_heartbeat
        # logging.info(f"[Rabbitmq] Init RabbitMQ Client: host={host}, port={port}, username={username}, password={password}, exchange={exchange}, queue_name={queue_name}, rabbitmq_ssl={rabbitmq_ssl}, rabbitmq_heartbeat={rabbitmq_heartbeat}")

    def send_task(self, message: str):
        queue_name = self.queue_name
        if queue_name is None:
            logging.error("[Rabbitmq] Queue name is None")
            return 
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            credentials=pika.PlainCredentials(self.username, self.password),
            ssl_options=pika.SSLOptions(ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)) if self.rabbitmq_ssl else None,
            heartbeat=self.rabbitmq_heartbeat)
        )
        # if queue_name == None:
        #     queue_name = self.queue_name
        logging.info(f"[Rabbitmq] Produce Send Task To Queue ({queue_name}): {message}")
        channel = connection.channel()
        
        # Declare the exchange
        channel.exchange_declare(exchange=self.exchange, exchange_type='direct', durable=True)

        # Declare the queue (ensure the queue is bound to the exchange)
        channel.queue_declare(queue=queue_name, durable=True)

        # Bind the queue to the exchange
        channel.queue_bind(exchange=self.exchange, queue=queue_name, routing_key=queue_name)

        channel.basic_publish(
            exchange=self.exchange,
            routing_key=queue_name,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        connection.close()
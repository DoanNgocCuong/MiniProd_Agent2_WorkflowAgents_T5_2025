import os, logging, argparse
import time
from src.channel.rabbitmq_consumer import RabbitMQConsumer
from src.channel.redis_client import RedisClient


def main():
    retry = 3
    for _ in range(retry):
        try:
            consumer = RabbitMQConsumer(
                host=os.getenv("RABBITMQ_HOST"),
                port=int(os.getenv("RABBITMQ_PORT")),
                username=os.getenv("RABBITMQ_USERNAME"),
                password=os.getenv("RABBITMQ_PASSWORD"),
                exchange=os.getenv("RABBITMQ_EXCHANGE"),
                queue_name=os.getenv("RABBITMQ_QUEUE"),
                redis_client=RedisClient(
                    host=os.getenv("REDIS_HOST"),
                    port=int(os.getenv("REDIS_PORT")),
                    password=os.getenv("REDIS_PASSWORD"),
                )
            )
            consumer.running_consumer()
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(10)
            continue


if __name__ == '__main__':
    main()
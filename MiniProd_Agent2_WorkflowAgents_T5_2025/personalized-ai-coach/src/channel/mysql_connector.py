import logging, json, os, traceback
import mysql.connector
from typing import List, Dict
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

class MysqlConnector:
    
    def get_connection(
        self, 
        host_name: str, 
        user_name: str, 
        user_password: str, 
        db_name: str, 
        port: int,
        **kwargs
    ) -> object:
        retry = kwargs.get('retry', 3)
        connection = None
        for _ in range(retry):
            try:
                connection = mysql.connector.connect(
                    host=host_name,
                    user=user_name,
                    passwd=user_password,
                    database=db_name,
                    port=port
                )
                logging.info("Connection to MySQL DB successful")
                break
            except Exception as e:
                time.sleep(10)
                logging.info(f"The error {traceback.format_exc()} occurred")
        return connection
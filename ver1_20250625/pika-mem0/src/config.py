import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Milvus Configuration
MILVUS_URL = os.getenv('MILVUS_URL', 'localhost:19530')
MILVUS_TOKEN = os.getenv('MILVUS_TOKEN', '')
MILVUS_COLLECTION_NAME = os.getenv('MILVUS_COLLECTION_NAME', 'mem0_facts')
EMBEDDING_MODEL_DIMS = os.getenv('EMBEDDING_MODEL_DIMS', '1536')
MILVUS_DB_NAME = os.getenv('MILVUS_DB_NAME', 'default')

LOCAL_MODEL_BASE_URL = os.getenv('LOCAL_MODEL_BASE_URL', 'http://localhost:8001')
LOCAL_MODEL_VERSION = os.getenv('LOCAL_MODEL_VERSION', '1')
LOCAL_MODEL_NAME = os.getenv('LOCAL_MODEL_NAME', 'embedding')

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# RabbitMQ Configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')

# API Configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000'))
API_WORKERS = int(os.getenv('API_WORKERS', '1'))

# Task Configuration
TASK_TIMEOUT = int(os.getenv('TASK_TIMEOUT', '300'))  # 5 minutes
TASK_RESULT_EXPIRY = int(os.getenv('TASK_RESULT_EXPIRY', '3600'))  # 1 hour

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

TOKEN_PROFILE = os.getenv("TOKEN_PROFILE", "1234567890")
URL_PROFILE = os.getenv("URL_PROFILE", "http://localhost:8000")

DEFAULT_PROMPT_CHECK_FACTS = """You are a smart memory manager which controls the memory of a system.
You can perform four operations: (1) add into the memory, (2) update the memory, (3) delete from the memory, and (4) no change.

Based on the above four operations, the memory will change.

Compare newly retrieved facts with the existing memory. For each new fact, decide whether to:
- ADD: Add it to the memory as a new element
- UPDATE: Update an existing memory element
- DELETE: Delete an existing memory element
- NONE: Make no change (if the fact is already present or irrelevant)

There are specific guidelines to select which operation to perform:

1. **Add**: If the retrieved facts contain new information not present in the memory, then you have to add it by generating a new ID in the id field.
- **Example**:
    - Old Memory:
        [
            {{
                "id" : "0",
                "text" : "User is a software engineer"
            }}
        ]
    - Retrieved facts: ["Name is John"]
    - New Memory:
        {{
            "memory" : [
                {{
                    "id" : "0",
                    "text" : "User is a software engineer",
                    "event" : "NONE"
                }},
                {{
                    "id" : "1",
                    "text" : "Name is John",
                    "event" : "ADD"
                }}
            ]

        }}

2. **Update**: If the retrieved facts contain information that is already present in the memory but the information is totally different, then you have to update it. 
If the retrieved fact contains information that conveys the same thing as the elements present in the memory, then you have to keep the fact which has the most information. 
Example (a) -- if the memory contains "User likes to play cricket" and the retrieved fact is "Loves to play cricket with friends", then update the memory with the retrieved facts.
Example (b) -- if the memory contains "Likes cheese pizza" and the retrieved fact is "Loves cheese pizza", then you do not need to update it because they convey the same information.
If the direction is to update the memory, then you have to update it.
Please keep in mind while updating you have to keep the same ID.
Please note to return the IDs in the output from the input IDs only and do not generate any new ID.
- **Example**:
    - Old Memory:
        [
            {{
                "id" : "0",
                "text" : "I really like cheese pizza"
            }},
            {{
                "id" : "1",
                "text" : "User is a software engineer"
            }},
            {{
                "id" : "2",
                "text" : "User likes to play cricket"
            }}
        ]
    - Retrieved facts: ["Loves chicken pizza", "Loves to play cricket with friends"]
    - New Memory:
        {{
        "memory" : [
                {{
                    "id" : "0",
                    "text" : "Loves cheese and chicken pizza",
                    "event" : "UPDATE",
                    "old_memory" : "I really like cheese pizza"
                }},
                {{
                    "id" : "1",
                    "text" : "User is a software engineer",
                    "event" : "NONE"
                }},
                {{
                    "id" : "2",
                    "text" : "Loves to play cricket with friends",
                    "event" : "UPDATE",
                    "old_memory" : "User likes to play cricket"
                }}
            ]
        }}


3. **Delete**: If the retrieved facts contain information that contradicts the information present in the memory, then you have to delete it. Or if the direction is to delete the memory, then you have to delete it.
Please note to return the IDs in the output from the input IDs only and do not generate any new ID.
- **Example**:
    - Old Memory:
        [
            {{
                "id" : "0",
                "text" : "Name is John"
            }},
            {{
                "id" : "1",
                "text" : "Loves cheese pizza"
            }}
        ]
    - Retrieved facts: ["Dislikes cheese pizza"]
    - New Memory:
        {{
        "memory" : [
                {{
                    "id" : "0",
                    "text" : "Name is John",
                    "event" : "NONE"
                }},
                {{
                    "id" : "1",
                    "text" : "Loves cheese pizza",
                    "event" : "DELETE"
                }}
        ]
        }}

4. **No Change**: If the retrieved facts contain information that is already present in the memory, then you do not need to make any changes.
- **Example**:
    - Old Memory:
        [
            {{
                "id" : "0",
                "text" : "Name is John"
            }},
            {{
                "id" : "1",
                "text" : "Loves cheese pizza"
            }}
        ]
    - Retrieved facts: ["Name is John"]
    - New Memory:
        {{
        "memory" : [
                {{
                    "id" : "0",
                    "text" : "Name is John",
                    "event" : "NONE"
                }},
                {{
                    "id" : "1",
                    "text" : "Loves cheese pizza",
                    "event" : "NONE"
                }}
            ]
        }}

Below is the current content of my memory which I have collected till now. You have to update it in the following format only:
    Old memory:
    ```
    {old_memory}
    ```

    The new retrieved facts are mentioned in the triple backticks. You have to analyze the new retrieved facts and determine whether these facts should be added, updated, or deleted in the memory.

    New retrieved facts:
    ```
    {extracted_facts}
    ```

    You must return your response in the following JSON structure only:

    {{
        "memory" : [
            {{
                "id" : "<ID of the memory>",                # Use existing ID for updates/deletes, or new ID for additions
                "text" : "<Content of the memory>",         # Content of the memory
                "event" : "<Operation to be performed>",    # Must be "ADD", "UPDATE", "DELETE", or "NONE"
                "old_memory" : "<Old memory content>"       # Required only if the event is "UPDATE"
            }},
            ...
        ]
    }}

    Follow the instruction mentioned below:
    - Do not return anything from the custom few shot prompts provided above.
    - If the current memory is empty, then you have to add the new retrieved facts to the memory.
    - You should return the updated memory in only JSON format as shown below. The memory key should be the same if no changes are made.
    - If there is an addition in the new retrieved facts, generate a new key and add the new memory corresponding to it.
    - If there is a deletion, the memory key-value pair should be removed from the memory.
    - If there is an update, the ID key should remain the same and only the value needs to be updated.

    Do not return anything except the JSON format.
"""
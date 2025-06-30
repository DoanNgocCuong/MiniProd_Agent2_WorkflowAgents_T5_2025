from src.config import (
    MILVUS_URL, 
    MILVUS_TOKEN, 
    MILVUS_COLLECTION_NAME, 
    EMBEDDING_MODEL_DIMS,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    TASK_RESULT_EXPIRY,
    LOCAL_MODEL_BASE_URL,
    LOCAL_MODEL_VERSION
)
from src.memory_processor import MemoryProcess
from mem0.memory.main import Memory
from mem0.configs.vector_stores.milvus import MetricType
import redis
import json
from typing import Dict, List
# Initialize Redis connection
from src.completions import Completions
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB
)

config = {
    "vector_store": {
        "provider": "milvus",
        "config": {
            "url": MILVUS_URL,
            "token": MILVUS_TOKEN,
            "metric_type": MetricType.COSINE,
            "collection_name": MILVUS_COLLECTION_NAME,
            "embedding_model_dims": int(EMBEDDING_MODEL_DIMS),
        },
    },
    "embedder": {
        "provider": "local_model",
        "config": {
            "model": "embedding",
            "embedding_dims": int(EMBEDDING_MODEL_DIMS),
            "local_model_base_url": LOCAL_MODEL_BASE_URL,
            "local_model_version": LOCAL_MODEL_VERSION,
        },
    },
    "version": "v1.1",
}

# Initialize MemoryProcess with configuration
memory_processor = MemoryProcess(
    memory_config=config
)

def extract_facts_worker(task_id: str, conversation: List[Dict], user_id: str, conversation_id: str, prompt: str = None) -> Dict:
    """
    Worker function to extract facts from a conversation
    
    Args:
        task_id: Unique identifier for the task
        conversation: List of conversation messages
        user_id: User identifier
        conversation_id: Conversation identifier
        prompt: Optional custom prompt for fact extraction
    """
    # Store results in Redis
    memory_processor = MemoryProcess(
        memory_config=config
    )
    facts = memory_processor.extract_facts(
            conversation=conversation,
            user_id=user_id,
            conversation_id=conversation_id,
            prompt=prompt,
        )
        
    # Convert facts to dictionary format for serialization
    result = {
        "status": "completed",
        "facts": [{
            "id": fact.id,
            "source": fact.source,
            "user_id": fact.user_id,
            "conversation_id": fact.conversation_id,
            "fact_type": fact.fact_type.value,
            "fact_value": fact.fact_value,
            "metadata": fact.metadata,
            "score": fact.score
        } for fact in facts]
    }

    redis_client.set(
        f"task_result_extract:{task_id}",
        json.dumps(result),
        ex=TASK_RESULT_EXPIRY
    )
    return result

def update_fact_worker(task_id: str, fact_id: str, content: str) -> Dict:
    """
    Worker function to update a fact in Milvus
    """
    memory_processor = MemoryProcess(
            memory_config=config
    )
    memory_processor.update_fact(fact_id, content)
    return {"status": "completed"}

def delete_fact_worker(task_id: str, fact_id: str) -> Dict:
    """
    Worker function to delete a fact from Milvus
    """
    memory_processor = MemoryProcess(
            memory_config=config
    )
    memory_processor.delete_fact(fact_id)
    return {"status": "completed"}

def search_facts_worker(task_id: str, query: str, user_id: str, conversation_id: str, limit: int) -> Dict:
    """
    Worker function to search for facts in Milvus
    """
    memory_processor = MemoryProcess(
            memory_config=config
    )
    facts = memory_processor.search_facts(query, user_id, conversation_id, limit)
    result = {
        "status": "completed",
        "facts": [{
            "id": fact.id,
            "source": fact.source,
            "user_id": fact.user_id,
            "conversation_id": fact.conversation_id,
            "fact_type": fact.fact_type.value,
            "fact_value": fact.fact_value,
            "metadata": fact.metadata,
            "score": fact.score
        } for fact in facts]
    }
    redis_client.set(
        f"task_result_retrieval:{task_id}",
        json.dumps(result),
        ex=TASK_RESULT_EXPIRY
    )
    return result


def generate_response_worker(task_id: str, messages: List[Dict], user_id: str, conversation_id: str, limit: int, mode: str) -> Dict:
    """
    Worker function to generate a response from a conversation
    """
    memory_processor = Memory.from_config(
        config
    )
    if isinstance(messages, str):
        messages = json.loads(messages)

    # Get user profiles from API (you'll need to implement this)
    
    # Generate base response
    completion = Completions(memory_processor)
    response, relevant_memories = completion.create(
        model="gpt-4o-mini",
        messages=messages,
        user_id=user_id,
        conversation_id=conversation_id,
        mode=mode,
    )
    
    response_txt = response.choices[0].message.content
    
    result = {
        "status": "completed",
        "response": response_txt,
        "relevant_memories": relevant_memories,
    }
    
    redis_client.set(
        f"task_result_generate_response:{task_id}",
        json.dumps(result),
        ex=TASK_RESULT_EXPIRY
    )
    return result

def extract_facts_without_save_worker(task_id: str, conversation: List[Dict], user_id: str, conversation_id: str, prompt: str = None) -> Dict:
    """
    Worker function to extract facts from a conversation without saving to vector DB
    
    Args:
        task_id: Unique identifier for the task
        conversation: List of conversation messages
        user_id: User identifier
        conversation_id: Conversation identifier
        prompt: Optional custom prompt for fact extraction
    """
    # Store results in Redis
    memory_processor = MemoryProcess(
        memory_config=config
    )
    facts = memory_processor.extract_facts_without_save(
        conversation=conversation,
        user_id=user_id,
        conversation_id=conversation_id,
        prompt=prompt,
    )
    print(f"FACT_EXTRACTED: {facts}")
    # Convert facts to dictionary format for serialization
    result = {
        "status": "completed",
        "facts": facts
    }

    redis_client.set(
        f"task_result_extract_without_save:{task_id}",
        json.dumps(result),
        ex=TASK_RESULT_EXPIRY
    )
    return result


def check_facts_worker(task_id: str, raw_facts: List[Dict], user_id: str, conversation_id: str = None, prompt: str = None ) -> Dict:
    """
    Worker function to check if the facts are already in the memory
    """
    if conversation_id:
        filters = {
            "user_id": user_id,
            "conversation_id": conversation_id,
        }
    else:
        filters = {
            "user_id": user_id,
        }
    memory_processor = MemoryProcess(
        memory_config=config
    )
    results = memory_processor.check_facts(raw_facts, user_id, prompt, filters)
    result = {
        "status": "completed",
        "results": results
    }
    redis_client.set(
        f"task_result_check_facts:{task_id}",
        json.dumps(result),
        ex=TASK_RESULT_EXPIRY
    )
    return result


def get_facts_worker(user_id: str, limit: int) -> Dict:
    """
    Worker function to get facts from Milvus
    """
    memory_processor = Memory.from_config(
        config
    )
    filters = {
        "user_id": user_id,
    }
    facts = memory_processor._get_all_from_vector_store(filters, limit)
    processed_facts = []
    for fact in facts:
        processed_facts.append({
            "id": fact.get("id"),
            "user_id": fact.get("user_id"),
            "fact": fact.get("memory"),
            "conversation_id": fact.get("metadata", {}).get("conversation_id")
        })

    result = {
        "status": "completed",
        "facts": processed_facts
    }
    return result
from typing import List, Dict
import json
from src.celery import celery_app
from src.workers import extract_facts_worker, update_fact_worker, delete_fact_worker, search_facts_worker, generate_response_worker, extract_facts_without_save_worker,check_facts_worker

@celery_app.task(queue="mem0_queue_extract_fact", bind = True)
def extract_facts_task(self, conversation: List[Dict], user_id: str, conversation_id: str) -> Dict:
    """
    Celery task to extract facts from a conversation and store results in Redis
    """
    try:
        task_id = self.request.id
        # Extract facts
        facts = extract_facts_worker(
            task_id=task_id,
            conversation=conversation,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return task_id

    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed",
            "error": error_message
        }
        raise

@celery_app.task(queue="mem0_queue_extract_fact", bind = True)
def update_fact_task(self, fact_id: str, content: str) -> Dict:
    """
    Celery task to update a fact in Milvus
    """
    try:
        task_id = self.request.id
        # Update fact
        update_fact_worker(
            task_id=task_id,
            fact_id=fact_id,
            content=content,
        )
        return task_id
    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed", 
            "error": error_message
        }
        raise

@celery_app.task(queue="mem0_queue_extract_fact", bind = True)
def delete_fact_task(self, fact_id: str) -> Dict:
    """
    Celery task to delete a fact from Milvus
    """
    try:
        task_id = self.request.id
        # Delete fact
        delete_fact_worker(
            task_id=task_id,
            fact_id=fact_id,
        )
        return task_id
    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed", 
            "error": error_message
        }   
        raise

@celery_app.task(queue="mem0_retrieval_queue", bind = True)
def search_facts_task(self, query: str, user_id: str, conversation_id: str, limit: int) -> Dict:
    """
    Celery task to search for facts in Milvus
    """ 
    try:
        task_id = self.request.id
        # Search for facts
        search_facts_worker(
            task_id=task_id,
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit,
        )
        return task_id  
    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed", 
            "error": error_message  
        }
        raise

@celery_app.task(queue="mem0_generate_response_queue", bind = True)
def generate_response_task(self, messages: List[Dict], user_id: str, conversation_id: str, mode: str) -> Dict:
    """
    Celery task to generate a response from a conversation
    """
    try:
        task_id = self.request.id
        # Generate response
        generate_response_worker(
            task_id=task_id,
            messages=messages,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=5,
            mode=mode,
        )
        return task_id
    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed", 
            "error": error_message
        }
        raise

@celery_app.task(queue="mem0_queue_extract_fact_test", bind = True)
def extract_facts_without_save_task(self, conversation: List[Dict], user_id: str, conversation_id: str, prompt: str = None) -> Dict:
    """
    Celery task to extract facts from a conversation without saving to vector DB
    
    Args:
        conversation: List of conversation messages
        user_id: User identifier
        conversation_id: Conversation identifier
        prompt: Optional custom prompt for fact extraction
    """
    try:
        task_id = self.request.id
        # Extract facts without saving
        facts = extract_facts_without_save_worker(
            task_id=task_id,
            conversation=conversation,
            user_id=user_id,
            conversation_id=conversation_id,
            prompt=prompt,
        )
        return task_id

    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed",
            "error": error_message
        }
        raise

@celery_app.task(queue="mem0_queue_check_facts_test", bind = True)
def check_facts_task(self, raw_facts: List[Dict], user_id: str, conversation_id: str = None, prompt: str = None) -> Dict:
    """
    Celery task to check if the facts are already in the memory
    """
    try:
        task_id = self.request.id
        # Check facts
        check_facts_worker(
            task_id=task_id,
            raw_facts=raw_facts,
            user_id=user_id,
            prompt=prompt,
            conversation_id=conversation_id,
        )
        return task_id
    except Exception as e:
        error_message = str(e)
        # Store error in Redis
        error_result = {
            "status": "failed",
            "error": error_message
        }
        raise
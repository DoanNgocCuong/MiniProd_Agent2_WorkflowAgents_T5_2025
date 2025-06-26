from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid
import logging
import json
import time
import redis
from src.config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    TASK_TIMEOUT,
)
from src.tasks import (
    extract_facts_task, 
    search_facts_task, 
    generate_response_task,
    extract_facts_without_save_task,
    check_facts_task
)
import asyncio
from src.models import (
    ConversationRequest, 
    SearchRequest, 
    FactResponse, 
    FactRetrievalResponse, 
    UserProfile,
    TestFactExtractionRequest,
    TestFactCheckingRequest,
    TestGetFactsRequest
)
from src.workers import get_facts_worker
from src.config import DEFAULT_PROMPT_CHECK_FACTS
# Configure logging
logger = logging.getLogger(__name__)

# Initialize Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB
)

app = FastAPI(title="Fact Extraction API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/extract_facts", response_model=Dict, tags=["production"])
async def extract_facts(request: ConversationRequest):
    # try:
        logger.info(f"Starting fact extraction for conversation: {request.conversation_id}")
        print(f"conversation: {request.conversation}")
        conversation = json.dumps(request.conversation,ensure_ascii=False)
        # Submit the task to Celery
        task = extract_facts_task.apply_async(
            args=[conversation, request.user_id, request.conversation_id],
        )
        print(f"task_extract: {task.id}")
        task_id = task.id
        start_time = time.time()
        
        while time.time() - start_time < TASK_TIMEOUT:
            # Check task status in Redis
            status_data = redis_client.get(f"task_result_extract:{task_id}")
            if status_data:
                status = json.loads(status_data)
                if status["status"] == "failed":
                    raise HTTPException(status_code=500, detail=status["message"])
                elif status["status"] == "completed":
                    # Get results from Redis
                    result_data = redis_client.get(f"task_result_extract:{task_id}")
                    if result_data:
                        result = json.loads(result_data)
                        if result["status"] == "completed":
                            print(f"result: {result}")
                            # Convert facts to response format
                            end_time = time.time()
                            time_response = end_time - start_time
                            return {
                                "status": "ok",
                                "time_response": time_response,
                                "facts": [FactResponse(**fact) for fact in result["facts"]]
                            }
            
            # Wait for a short time before checking again
            await asyncio.sleep(0.1)
        
        # If we get here, the task took too long
        raise HTTPException(
            status_code=408,
            detail="Fact extraction is taking longer than expected. Please try again later."
        )
        
    # except Exception as e:
    #     logger.error(f"Error in fact extraction: {str(e)}")
    #     raise HTTPException(status_code=500, detail=str(e))

@app.post("/search_facts", response_model=Dict, tags=["production"])
async def search_facts(request: SearchRequest):
    # try:
        logger.info(f"Searching facts with query: {request.query}")
        
        # Search for facts
        result = search_facts_task.apply_async(
            args=[request.query, request.user_id, request.conversation_id, request.limit],
        )
        print(f"task_retrieval: {result.id}")
        task_id = result.id
        start_time = time.time()
        
        while time.time() - start_time < TASK_TIMEOUT:
            # Check task status in Redis
            status_data = redis_client.get(f"task_result_retrieval:{task_id}")
            if status_data:
                status = json.loads(status_data)
                if status["status"] == "failed":
                    raise HTTPException(status_code=500, detail=status["message"])
                elif status["status"] == "completed":
                    # Get results from Redis
                    result_data = redis_client.get(f"task_result_retrieval:{task_id}")
                    if result_data:
                        result = json.loads(result_data)
                        if result["status"] == "completed":
                            # Convert facts to response format
                            end_time = time.time()
                            time_response = end_time - start_time
                            facts = []
                            for fact in result["facts"]:
                                fact_response = FactRetrievalResponse(
                                    id=fact.get("id", None),
                                    source=fact.get("source", None),
                                    user_id=fact.get("user_id", None),
                                    conversation_id=fact.get("conversation_id", None),
                                    fact_type=fact.get("fact_type", None),
                                    fact_value=fact.get("fact_value", None),
                                    metadata=fact.get("metadata", None)
                                )
                                fact_response.operation = "retrieval"
                                facts.append(fact_response)
                            return {
                                "status": "ok",
                                "time_response": time_response,
                                "facts": facts
                            }
            
            # Wait for a short time before checking again
            await asyncio.sleep(0.1)
        
        # If we get here, the task took too long
        raise HTTPException(
            status_code=408,
            detail="Fact retrieval is taking longer than expected. Please try again later."
        )
    # except Exception as e:
    #     logger.error(f"Error searching facts: {str(e)}")
    #     raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_response", tags=["production"])
async def generate_response(request: ConversationRequest):
    # try:
        logger.info(f"Generating response for conversation: {request.conversation_id}")
        conversation = json.dumps(request.conversation,ensure_ascii=False)
        print(f"conversation: {conversation}")
        # Submit the task to Celery
        task = generate_response_task.apply_async(
            args=[conversation, request.user_id, request.conversation_id, request.mode],
        )
        print(f"task_generate_response: {task.id}")
        task_id = task.id
        start_time = time.time()    

        while time.time() - start_time < TASK_TIMEOUT:
            # Check task status in Redis
            status_data = redis_client.get(f"task_result_generate_response:{task_id}")
            if status_data:
                status = json.loads(status_data)    
                if status["status"] == "failed":
                    raise HTTPException(status_code=500, detail=status["message"])
                elif status["status"] == "completed":
                    # Get results from Redis
                    result_data = redis_client.get(f"task_result_generate_response:{task_id}")
                    if result_data: 
                        result = json.loads(result_data)
                        if result["status"] == "completed":
                            relevant_memories = result.get("relevant_memories", [])
                            print(f"relevant_memories: {relevant_memories}")
                            # Convert facts to response format
                            end_time = time.time()
                            time_response = end_time - start_time
                            return {
                                "status": "ok",
                                "time_response": time_response,
                                "response": result["response"],
                                "relevant_memories": relevant_memories
                            }
            
            # Wait for a short time before checking again   
            await asyncio.sleep(0.1)
        
        # If we get here, the task took too long
        raise HTTPException(
            status_code=408,
            detail="Response generation is taking longer than expected. Please try again later."
        )   


@app.post("/test/test_extract_facts", response_model=Dict, tags=["test"])
async def test_extract_facts(request: TestFactExtractionRequest):
    try:
        logger.info(f"Testing fact extraction")
        if isinstance(request.conversation, str):
            conversation = json.loads(request.conversation)
        else:
            conversation = request.conversation
        
        # Submit the task to Celery with the custom prompt
        task = extract_facts_without_save_task.apply_async(
            args=[conversation, request.user_id, request.conversation_id, request.prompt],
        )
        
        task_id = task.id
        start_time = time.time()
        
        while time.time() - start_time < TASK_TIMEOUT:
            # Check task status in Redis
            status_data = redis_client.get(f"task_result_extract_without_save:{task_id}")
            if status_data:
                status = json.loads(status_data)
                if status["status"] == "failed":
                    raise HTTPException(status_code=500, detail=status["message"])
                elif status["status"] == "completed":
                    # Get results from Redis
                    result_data = redis_client.get(f"task_result_extract_without_save:{task_id}")
                    if result_data:
                        result = json.loads(result_data)
                        if result["status"] == "completed":
                            # Convert facts to response format
                            end_time = time.time()
                            time_response = end_time - start_time
                            return {
                                "status": "ok",
                                "time_response": time_response,
                                "facts": result.get("facts", [])
                            }
            
            # Wait for a short time before checking again
            await asyncio.sleep(0.1)
        
        # If we get here, the task took too long
        raise HTTPException(
            status_code=408,
            detail="Fact extraction is taking longer than expected. Please try again later."
        )
        
    except Exception as e:
        logger.error(f"Error in test fact extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))   

@app.post("/test/test_check_facts", response_model=Dict, tags=["test"])
async def test_check_facts(request: TestFactCheckingRequest):
    try:
        logger.info(f"Testing fact checking")
        # raw_facts = json.dumps(request.raw_facts, ensure_ascii=False)
        try:
            if isinstance(request.raw_facts, str):
                raw_facts = json.loads(request.raw_facts)
            else:
                raw_facts = request.raw_facts
        except Exception as e:
            logger.error(f"Error in test fact checking: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
        # Submit the task to Celery with the custom prompt
        task = check_facts_task.apply_async(
            args=[raw_facts, request.user_id, request.conversation_id, request.prompt],
        )
        
        task_id = task.id
        start_time = time.time()
        
        while time.time() - start_time < TASK_TIMEOUT:
            # Check task status in Redis
            status_data = redis_client.get(f"task_result_check_facts:{task_id}")
            if status_data:
                status = json.loads(status_data)
                if status["status"] == "failed":
                    raise HTTPException(status_code=500, detail=status["message"])
                elif status["status"] == "completed":
                    result_data = redis_client.get(f"task_result_check_facts:{task_id}")
                    if result_data:
                        result = json.loads(result_data)
                        if result["status"] == "completed":
                            # Convert facts to response format
                            end_time = time.time()
                            time_response = end_time - start_time
                            return {
                                "status": "ok",
                                "time_response": time_response,
                                "results": result.get("results", [])
                            }
            
            # Wait for a short time before checking again
            await asyncio.sleep(0.1)
        
        # If we get here, the task took too long
        raise HTTPException(
            status_code=408,
            detail="Fact extraction is taking longer than expected. Please try again later."
        )
        
    except Exception as e:
        logger.error(f"Error in test fact checking: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 


@app.get("/test/default_checking_prompt", response_model=Dict, tags=["test"])
async def get_checking_prompt():
    return {
        "status": "ok",
        "prompt": DEFAULT_PROMPT_CHECK_FACTS
    }


# create api to get fact from milvus using user id only
@app.get("/test/get_facts", response_model=Dict, tags=["test"])
async def get_facts(user_id: str, limit: int = 100):
    try:
        logger.info(f"Getting facts for user: {user_id}")
        # get facts from milvus using user id
        facts = get_facts_worker(user_id, limit)
        if facts.get("status") == "completed":  
            return {
                "status": "ok",
                "facts": facts.get("facts", [])
            }
        else:
            raise HTTPException(status_code=500, detail=facts.get("message", "Error getting facts"))
    except Exception as e:
        logger.error(f"Error in getting facts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
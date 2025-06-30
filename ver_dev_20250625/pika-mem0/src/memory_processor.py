import logging
from typing import Dict, List, Optional, Union
import uuid
import numpy as np
import json
from sklearn.metrics.pairwise import cosine_similarity
from src.config import LOCAL_MODEL_BASE_URL
from mem0.memory.main import Memory
from src.models import FactRetrievalResponse, FactType, UserProfile
from OpenAITriton.openai_triton import OpenAITriton
from mem0.memory.utils import (
    get_fact_retrieval_messages,
    parse_messages,
    remove_code_blocks
)
from mem0.configs.prompts import get_update_memory_message_custom

logger = logging.getLogger(__name__)


class MemoryProcess:
    def __init__(
        self,
        memory_config: dict = None
    ):
        """Initialize MemoryProcess with Milvus and mem0 configuration.
        
        Args:
            milvus_url (str): Full URL for Milvus/Zilliz server
            milvus_token (str): Token/api_key for Zilliz server
            collection_name (str): Name of the Milvus collection
            embedding_model_dims (int): Dimensions of the embedding model
            memory_config (Optional[MemoryConfig]): Configuration for mem0 Memory
        """
        print(memory_config)
        self.memory_config = memory_config
        # Initialize mem0 Memory with default or provided config
        self.memory = Memory.from_config(self.memory_config)
        self.embedder = OpenAITriton(url=LOCAL_MODEL_BASE_URL, model_version="1")
        
    def extract_facts(
        self, 
        conversation: List[Dict], 
        user_id: str,
        conversation_id: str,
        prompt: str = None,
    ) -> List[FactRetrievalResponse]:
        """Extract facts from text using mem0.
        
        Args:
            conversation (List[Dict]): List of conversation messages
            user_id (str): ID of the user
            conversation_id (str): ID of the conversation
            prompt (Optional[str]): Custom prompt for fact extraction
            
        Returns:
            List[FactRetrievalResponse]: List of extracted facts
        """
        # Initialize memory if not already initialized
        
        # Prepare metadata with user and conversation information
        enhanced_metadata = {}
        enhanced_metadata.update({
            "user_id": user_id,
            "conversation_id": conversation_id,
        })
        
        # Use mem0 to extract facts with custom prompt if provided
        result = self.memory.add(
            messages=conversation,
            user_id=user_id,
            metadata=enhanced_metadata,
            prompt=prompt
        )
        print(result)
        facts = []
        new_memories = result.get("results", [])
        last_retrieved_facts = new_memories[-1].get("retrieved_facts", [])
        memories_operations = new_memories[-1].get("memories_operations", {})
        if last_retrieved_facts:
            for memory in last_retrieved_facts:
                fact = FactRetrievalResponse(
                    id=str(uuid.uuid4()),
                    source="conversation",
                    user_id=user_id,
                    conversation_id=conversation_id,
                    fact_type=FactType.OTHER,
                    fact_value=memory,  # Using content as fact_value by default
                    metadata={},
                    operation=memories_operations.get(memory, {}).get("operation", "NONE"),
                    score=0
                )
                facts.append(fact)
            
        return facts
    
    def extract_facts_without_save(
        self, 
        conversation: List[Dict], 
        user_id: str,
        conversation_id: str,
        prompt: str = None,
    ) -> List[FactRetrievalResponse]:
        """Extract facts from text using mem0 without saving to vector DB.
        
        Args:
            conversation (List[Dict]): List of conversation messages
            user_id (str): ID of the user
            conversation_id (str): ID of the conversation
            prompt (Optional[str]): Custom prompt for fact extraction
            
        Returns:
            List[FactRetrievalResponse]: List of extracted facts
        """
        parsed_messages = parse_messages(conversation)
        if prompt:
            system_prompt = prompt
            user_prompt = f"Input:\n{parsed_messages}"
        else:
            system_prompt, user_prompt = get_fact_retrieval_messages(parsed_messages)

        response = self.memory.llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        # print(f"response: {response}")

        try:
            response = remove_code_blocks(response)
            new_retrieved_facts = json.loads(response)["facts"]
        except Exception as e:
            logging.error(f"Error in new_retrieved_facts: {e}")
            new_retrieved_facts = []
            
        return new_retrieved_facts

    def check_facts(
        self,
        raw_facts: List,
        user_id: str,
        prompt: str = None,
        filters: dict = None,
    ) -> Dict:
        """Check if the facts are already in the memory."""
        if raw_facts:
            new_message_embeddings = {}
            retrieved_old_memory = []
            for new_mem in raw_facts:
                messages_embeddings = self.memory.embedding_model.embed(new_mem, "add")
                new_message_embeddings[new_mem] = messages_embeddings
                existing_memories = self.memory.vector_store.search(
                    query=new_mem,
                    vectors=messages_embeddings,
                    limit=10,
                    filters=filters,
                )
                for mem in existing_memories:
                    retrieved_old_memory.append({"id": mem.id, "text": mem.payload["data"]})
            unique_data = {}
            for item in retrieved_old_memory:
                unique_data[item["id"]] = item
            retrieved_old_memory = list(unique_data.values())
            logging.info(f"Total existing memories: {len(retrieved_old_memory)}")

            # mapping UUIDs with integers for handling UUID hallucinations
            temp_uuid_mapping = {}
            for idx, item in enumerate(retrieved_old_memory):
                temp_uuid_mapping[str(idx)] = item["id"]
                retrieved_old_memory[idx]["id"] = str(idx)

            function_calling_prompt = get_update_memory_message_custom(
                retrieved_old_memory, raw_facts, prompt
            )
            print(f"function_calling_prompt: {function_calling_prompt}")
            try:
                new_memories_with_actions = self.memory.llm.generate_response(
                    messages=[{"role": "user", "content": function_calling_prompt}],
                    response_format={"type": "json_object"},
                )
                print(f"new_memories_with_actions: {new_memories_with_actions}")
            except Exception as e:
                logging.error(f"Error in new_memories_with_actions: {e}")
                new_memories_with_actions = []

            try:
                new_memories_with_actions = remove_code_blocks(new_memories_with_actions)
                new_memories_with_actions = json.loads(new_memories_with_actions)
            except Exception as e:
                logging.error(f"Invalid JSON response: {e}")
                new_memories_with_actions = []
            return {
                "new_memories_with_actions": new_memories_with_actions,
                "retrieved_old_memory": retrieved_old_memory,
            }
        
    def search_facts(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        fact_type: Optional[FactType] = None,
        limit: int = 5, 
        filters: Optional[Dict] = None,
        score_threshold: float = 0.1
    ) -> List[FactRetrievalResponse]:
        """Search for facts in Milvus.
        
        Args:
            query (str): Search query
            user_id (Optional[str]): Filter by user ID
            conversation_id (Optional[str]): Filter by conversation ID
            fact_type (Optional[FactType]): Filter by fact type
            limit (int): Maximum number of results
            filters (Optional[Dict]): Additional filters
            score_threshold (float): Minimum score threshold for facts (default: 0.6)
            
        Returns:
            List[Fact]: List of matching facts with scores >= score_threshold
        """
        # Initialize memory if not already initialized
        
        # Search in Milvus
        print("starting search")
        results = self.memory.search(
            query=query,
            user_id=user_id,
            limit=limit,
        )
        print(results)
        # Convert results to Fact objects and filter by score
        facts = []
        results = results.get("results", [])
        for result in results:
            score = result.get("score", 0)
            # Only include facts with score >= score_threshold
            if score >= score_threshold:
                fact = FactRetrievalResponse(
                    id=result.get("id", str(uuid.uuid4())),                
                    source=result.get("source", ""),
                    user_id=result.get("user_id", ""),
                    conversation_id=result.get("metadata", {}).get("conversation_id", ""),
                    fact_type=FactType(result.get("metadata", {}).get("fact_type", FactType.OTHER.value)),
                    fact_value=result.get("memory", ""),
                    metadata=result.get("metadata", {}),
                    score=score
                )
                facts.append(fact)
        
        logger.info(f"Found {len(facts)} facts with score >= {score_threshold} out of {len(results)} total results")
        return facts
    
    
    def update_fact(
        self, 
        fact_id: str, 
        content: Optional[str] = None, 
    ) -> None:
        """Update a fact in Milvus.
        
        Args:
            fact_id (str): ID of the fact to update
            content (Optional[str]): New content for the fact
            fact_type (Optional[FactType]): New fact type
            fact_value (Optional[str]): New fact value
            metadata (Optional[Dict]): New metadata for the fact
        """
        # Initialize memory if not already initialized
        
        res = self.memory.update(fact_id, content)
        return res
        
    def delete_fact(self, fact_id: str) -> None:
        """Delete a fact from Milvus.
        
        Args:
            fact_id (str): ID of the fact to delete
        """
        # Initialize memory if not already initialized

        res = self.memory.delete(fact_id)
        return res

    def embed_user_profile(self, profile: UserProfile) -> List[float]:
        """
        Embed user profile data by concatenating key-value pairs
        """
        # embedding each key-value pair in the profile separately
        embeddings = []
        for key, value in profile.profile_data.items():
            text = f"{key}: {value}"
            embedding = self.embedder.create_embedding(model="embedding", input=text).data[0].embedding
            embeddings.append(embedding)
        return embeddings

    def match_user_profiles(self, query: str, profiles: List[UserProfile], top_k: int = 1) -> List[UserProfile]:
        """
        Match user profiles based on query similarity
        """
        # Embed the query
        query_embedding = self.embedder.create_embedding(model="embedding", input=query).data[0].embedding
        
        # Embed all profiles if not already embedded
        for profile in profiles:
            if profile.embedding is None:
                profile.embedding = self.embed_user_profile(profile)
        
        # Calculate cosine similarity
        for profile in profiles:
            similarity = cosine_similarity(
                [query_embedding],
                [profile.embedding]
            )[0][0]
            profile.score = float(similarity)
        
        # Sort by similarity score and return top k
        matched_profiles = sorted(profiles, key=lambda x: x.score, reverse=True)[:top_k]
        return matched_profiles

    def personalize_response(self, response: str, profile: UserProfile) -> str:
        """
        Personalize the response based on user profile
        """
        # Add profile context to the response
        profile_context = " ".join([f"{k}: {v}" for k, v in profile.profile_data.items()])
        personalized_response = f"{response}\n\nBased on your profile ({profile_context}), I've tailored this response to better suit your needs."
        return personalized_response

import logging
from typing import Dict, List, Optional, Union
import uuid
from enum import Enum

from pydantic import BaseModel

from mem0.configs.base import MemoryConfig
from mem0.memory.main import Memory
from mem0.vector_stores.milvus import MilvusDB

logger = logging.getLogger(__name__)

class FactType(str, Enum):
    """Types of facts that can be extracted"""
    ENTITY = "entity"  # Named entities, people, places, organizations
    RELATION = "relation"  # Relationships between entities
    ATTRIBUTE = "attribute"  # Attributes or properties of entities
    EVENT = "event"  # Events or actions
    CONCEPT = "concept"  # General concepts or ideas
    NUMERIC = "numeric"  # Numerical facts or statistics
    TEMPORAL = "temporal"  # Time-related facts
    SPATIAL = "spatial"  # Location or spatial facts
    CAUSAL = "causal"  # Cause-effect relationships
    OTHER = "other"  # Other types of facts

class Fact(BaseModel):
    """Model for storing extracted facts"""
    id: str
    content: str
    source: str
    user_id: str
    conversation_id: str
    fact_type: FactType
    fact_value: str
    metadata: Dict
    embedding: Optional[List[float]] = None

class MemoryProcess:
    def __init__(
        self,
        milvus_url: str,
        milvus_token: str,
        collection_name: str = "mem0_facts",
        embedding_model_dims: int = 1536,
        memory_config: Optional[MemoryConfig] = None
    ):
        """Initialize MemoryProcess with Milvus and mem0 configuration.
        
        Args:
            milvus_url (str): Full URL for Milvus/Zilliz server
            milvus_token (str): Token/api_key for Zilliz server
            collection_name (str): Name of the Milvus collection
            embedding_model_dims (int): Dimensions of the embedding model
            memory_config (Optional[MemoryConfig]): Configuration for mem0 Memory
        """
        self.milvus = MilvusDB(
            url=milvus_url,
            token=milvus_token,
            collection_name=collection_name,
            embedding_model_dims=embedding_model_dims
        )
        
        # Initialize mem0 Memory with default or provided config
        self.memory = Memory(memory_config or MemoryConfig())
        
    def extract_facts(
        self, 
        text: str, 
        source: str, 
        user_id: str,
        conversation_id: str,
        fact_type: FactType = FactType.OTHER,
        metadata: Optional[Dict] = None
    ) -> List[Fact]:
        """Extract facts from text using mem0.
        
        Args:
            text (str): Text to extract facts from
            source (str): Source of the text
            user_id (str): ID of the user
            conversation_id (str): ID of the conversation
            fact_type (FactType): Type of fact to extract
            metadata (Optional[Dict]): Additional metadata
            
        Returns:
            List[Fact]: List of extracted facts
        """
        # Use mem0 to extract facts
        result = self.memory.add(
            messages=[{"role": "user", "content": text}],
            user_id=user_id,
            metadata=metadata or {}
        )
        
        facts = []
        for memory in result.get("results", {}).get("add", []):
            fact = Fact(
                id=str(uuid.uuid4()),
                content=memory.get("content", ""),
                source=source,
                user_id=user_id,
                conversation_id=conversation_id,
                fact_type=fact_type,
                fact_value=memory.get("content", ""),  # Using content as fact_value by default
                metadata=memory.get("metadata", {}),
                embedding=memory.get("embedding")
            )
            facts.append(fact)
            
        return facts
    
    def store_facts(self, facts: List[Fact]) -> None:
        """Store extracted facts in Milvus.
        
        Args:
            facts (List[Fact]): List of facts to store
        """
        if not facts:
            return
            
        # Prepare data for Milvus
        ids = [fact.id for fact in facts]
        vectors = [fact.embedding for fact in facts]
        payloads = [
            {
                "content": fact.content,
                "source": fact.source,
                "user_id": fact.user_id,
                "conversation_id": fact.conversation_id,
                "fact_type": fact.fact_type.value,
                "fact_value": fact.fact_value,
                **fact.metadata
            }
            for fact in facts
        ]
        
        # Insert into Milvus
        self.milvus.insert(ids=ids, vectors=vectors, payloads=payloads)
        
    def search_facts(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        fact_type: Optional[FactType] = None,
        limit: int = 5, 
        filters: Optional[Dict] = None
    ) -> List[Fact]:
        """Search for facts in Milvus.
        
        Args:
            query (str): Search query
            user_id (Optional[str]): Filter by user ID
            conversation_id (Optional[str]): Filter by conversation ID
            fact_type (Optional[FactType]): Filter by fact type
            limit (int): Maximum number of results
            filters (Optional[Dict]): Additional filters
            
        Returns:
            List[Fact]: List of matching facts
        """
        # Get query embedding from mem0
        query_embedding = self.memory.embedding_model.embed(query)
        
        # Prepare filters
        search_filters = filters or {}
        if user_id:
            search_filters["user_id"] = user_id
        if conversation_id:
            search_filters["conversation_id"] = conversation_id
        if fact_type:
            search_filters["fact_type"] = fact_type.value
        
        # Search in Milvus
        results = self.milvus.search(
            query=query,
            vectors=query_embedding,
            limit=limit,
            filters=search_filters
        )
        
        # Convert results to Fact objects
        facts = []
        for result in results:
            fact = Fact(
                id=result.id,
                content=result.payload.get("content", ""),
                source=result.payload.get("source", ""),
                user_id=result.payload.get("user_id", ""),
                conversation_id=result.payload.get("conversation_id", ""),
                fact_type=FactType(result.payload.get("fact_type", FactType.OTHER.value)),
                fact_value=result.payload.get("fact_value", ""),
                metadata={k:v for k,v in result.payload.items() if k not in ["content", "source", "user_id", "conversation_id", "fact_type", "fact_value"]},
                embedding=None  # We don't store embeddings in results
            )
            facts.append(fact)
            
        return facts
    
    def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Retrieve a specific fact by ID.
        
        Args:
            fact_id (str): ID of the fact to retrieve
            
        Returns:
            Optional[Fact]: The retrieved fact or None if not found
        """
        result = self.milvus.get(fact_id)
        if not result:
            return None
            
        return Fact(
            id=result.id,
            content=result.payload.get("content", ""),
            source=result.payload.get("source", ""),
            user_id=result.payload.get("user_id", ""),
            conversation_id=result.payload.get("conversation_id", ""),
            fact_type=FactType(result.payload.get("fact_type", FactType.OTHER.value)),
            fact_value=result.payload.get("fact_value", ""),
            metadata={k:v for k,v in result.payload.items() if k not in ["content", "source", "user_id", "conversation_id", "fact_type", "fact_value"]},
            embedding=None
        )
    
    def update_fact(
        self, 
        fact_id: str, 
        content: Optional[str] = None, 
        fact_type: Optional[FactType] = None,
        fact_value: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Update a fact in Milvus.
        
        Args:
            fact_id (str): ID of the fact to update
            content (Optional[str]): New content for the fact
            fact_type (Optional[FactType]): New fact type
            fact_value (Optional[str]): New fact value
            metadata (Optional[Dict]): New metadata for the fact
        """
        current_fact = self.get_fact(fact_id)
        if not current_fact:
            raise ValueError(f"Fact with ID {fact_id} not found")
            
        # Update fields if provided
        if content:
            current_fact.content = content
        if fact_type:
            current_fact.fact_type = fact_type
        if fact_value:
            current_fact.fact_value = fact_value
        if metadata:
            current_fact.metadata.update(metadata)
            
        # Get new embedding if content changed
        if content:
            current_fact.embedding = self.memory.embedding_model.embed(content)
            
        # Update in Milvus
        self.milvus.update(
            vector_id=fact_id,
            vector=current_fact.embedding,
            payload={
                "content": current_fact.content,
                "source": current_fact.source,
                "user_id": current_fact.user_id,
                "conversation_id": current_fact.conversation_id,
                "fact_type": current_fact.fact_type.value,
                "fact_value": current_fact.fact_value,
                **current_fact.metadata
            }
        )
        
    def delete_fact(self, fact_id: str) -> None:
        """Delete a fact from Milvus.
        
        Args:
            fact_id (str): ID of the fact to delete
        """
        self.milvus.delete(fact_id)
        
    def list_facts(
        self, 
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        fact_type: Optional[FactType] = None,
        filters: Optional[Dict] = None, 
        limit: int = 100
    ) -> List[Fact]:
        """List all facts in Milvus.
        
        Args:
            user_id (Optional[str]): Filter by user ID
            conversation_id (Optional[str]): Filter by conversation ID
            fact_type (Optional[FactType]): Filter by fact type
            filters (Optional[Dict]): Additional filters
            limit (int): Maximum number of results
            
        Returns:
            List[Fact]: List of facts
        """
        # Prepare filters
        search_filters = filters or {}
        if user_id:
            search_filters["user_id"] = user_id
        if conversation_id:
            search_filters["conversation_id"] = conversation_id
        if fact_type:
            search_filters["fact_type"] = fact_type.value
            
        results = self.milvus.list(filters=search_filters, limit=limit)
        
        facts = []
        for result in results[0]:  # list() returns a list of lists
            fact = Fact(
                id=result.id,
                content=result.payload.get("content", ""),
                source=result.payload.get("source", ""),
                user_id=result.payload.get("user_id", ""),
                conversation_id=result.payload.get("conversation_id", ""),
                fact_type=FactType(result.payload.get("fact_type", FactType.OTHER.value)),
                fact_value=result.payload.get("fact_value", ""),
                metadata={k:v for k,v in result.payload.items() if k not in ["content", "source", "user_id", "conversation_id", "fact_type", "fact_value"]},
                embedding=None
            )
            facts.append(fact)
            
        return facts 
    
from pydantic import BaseModel
from typing import List, Dict, Optional, Union
from enum import Enum   
from src.config import DEFAULT_PROMPT_CHECK_FACTS

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


class ConversationRequest(BaseModel):
    user_id: str
    conversation_id: str
    conversation: List[Dict]
    mode: str = "milvus_only"

class SearchRequest(BaseModel):
    query: str
    user_id: str
    conversation_id: str
    limit: Optional[int] = 5

class FactResponse(BaseModel):
    id: str
    source: str
    user_id: str
    conversation_id: str
    fact_type: FactType = None
    fact_value: str = None
    operation: str = None
    metadata: Dict = None

class FactRetrievalResponse(BaseModel):
    id: str
    source: str
    user_id: str
    conversation_id: str
    fact_type: FactType
    fact_value: str
    score: float
    metadata: Dict

class UserProfile(BaseModel):
    conversation_id: str
    profile_data: Dict[str, str]  # key-value pairs of profile information
    embedding: Optional[List[float]] = None  # vector embedding of the profile
    score: Optional[float] = None  # similarity score when matched

    # print profile_data
    def __str__(self):
        return f"UserProfile(conversation_id={self.conversation_id}, profile_data={self.profile_data}, score={self.score})"

class TestFactExtractionRequest(BaseModel):
    conversation: List[Dict]
    prompt: str
    user_id: str = "test_user"
    conversation_id: str = "test_conversation"


class TestFactCheckingRequest(BaseModel):
    raw_facts: Union[str, List]
    prompt: str = DEFAULT_PROMPT_CHECK_FACTS
    user_id: str = "test_user"
    conversation_id: str = None


class TestGetFactsRequest(BaseModel):
    user_id: str
    limit: int = 100

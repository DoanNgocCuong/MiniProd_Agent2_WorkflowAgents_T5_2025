from typing import List, Optional, Union

from pydantic import BaseModel, Field


class OpenAITextEmbeddingResponseDataItem(BaseModel):
    embedding: List[float]


class OpenAITextEmbeddingResponse(BaseModel):
    data: List[OpenAITextEmbeddingResponseDataItem] = Field()
    model: str = ""


class CohereV2RerankResponseResultsItem(BaseModel):
    document: Union[str, None] = None
    index: int = Field()
    relevance_score: float = Field()
    rank: int = Field()


class CohereV2RerankResponse(BaseModel):
    id: Optional[Union[str, None]] = None
    results: List[CohereV2RerankResponseResultsItem] = Field()
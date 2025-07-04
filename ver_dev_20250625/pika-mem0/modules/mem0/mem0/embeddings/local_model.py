from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase
from OpenAITriton.openai_triton import OpenAITriton


class LocalModelEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "text-embedding-3-small"
        self.config.embedding_dims = self.config.embedding_dims or 1024

        # Initialize OpenAITriton client
        self.client = OpenAITriton(
            url=self.config.local_model_base_url or "localhost:8001",
            model_version=self.config.local_model_version or "1"
        )

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using OpenAITriton.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        response = self.client.create_embedding(model=self.config.model, input=text)
        return response.data[0].embedding
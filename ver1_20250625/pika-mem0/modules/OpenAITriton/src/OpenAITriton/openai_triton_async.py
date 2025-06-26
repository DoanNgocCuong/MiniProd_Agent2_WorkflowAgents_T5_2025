import asyncio
import traceback
from typing import Dict, List, Union

import numpy as np
import requests
import tritonclient.grpc.aio as grpcclient
from transformers import AutoTokenizer

from .model import (
    CohereV2RerankResponse,
    CohereV2RerankResponseResultsItem,
    OpenAITextEmbeddingResponse,
    OpenAITextEmbeddingResponseDataItem,
)


class AsyncOpenAITriton:
    """An async Triton client that is OpenAI-embedding-api compatible and Cohere-rerank-api compatible"""

    def __init__(self, url: str, model_version: str = "1"):
        """Initialize an async Triton client

        Parameters
        ----------
        url : str
            e.g `localhost:8001`
        model_version : str, optional
            Version of the model, by default "1"
        """
        self.url = url.strip("/")
        self.model_version = model_version
        self.rerank_tokenizer = AutoTokenizer.from_pretrained(
            "jinaai/jina-reranker-v2-base-multilingual",
            trust_remote_code=True,
        )

    async def create_embedding(self, model: str, input: Union[str, List[str]]) -> OpenAITextEmbeddingResponse:
        """Generate embedding(s) of a text or a list of text

        Parameters
        ----------
        model : str
            name of deployed model
        input : Union[str, List[str]]
            a text or list of text

        Returns
        -------
        OpenAITextEmbeddingResponse
            see OpenAI text embedding api docs

        Raises
        ------
        Exception
            triton inference request fails
        ValueError
            input text must be a string or a list of strings
        """
        input_text = []
        if isinstance(input, str):
            input_text.append(input)
        else:
            input_text = input
        if input_text:
            try:
                # Create triton client in the method to ensure it uses the correct event loop
                triton_client = grpcclient.InferenceServerClient(url=self.url)
                inputs = []
                outputs = []
                for text in input_text:
                    raw_text = np.array([[text]], dtype=object)  # shape: [1, 1]
                    infer_input = grpcclient.InferInput("text", raw_text.shape, "BYTES")
                    infer_input.set_data_from_numpy(raw_text)
                    text_embeds = grpcclient.InferRequestedOutput("embeddings")
                    inputs.append(infer_input)
                    outputs.append(text_embeds)

                embeddings = []
                tasks = [
                    triton_client.infer(model_name=model, inputs=[inputs[i]], outputs=None) for i in range(len(inputs))
                ]
                results = await asyncio.gather(*tasks)
                for response in results:
                    embedding = OpenAITextEmbeddingResponseDataItem(
                        embedding=response.as_numpy("embeddings")[0].tolist()
                    )
                    embeddings.append(embedding)
                output = OpenAITextEmbeddingResponse(data=embeddings, model=model)
                return output
            except Exception as e:
                traceback.print_exc()
                raise Exception(f"Error during inference: {str(e)}")
        else:
            raise ValueError("Input text must be a string or a list of strings.")

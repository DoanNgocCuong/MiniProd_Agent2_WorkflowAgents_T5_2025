import traceback
from typing import List, Union

import numpy as np
import tritonclient.grpc as grpcclient

from .model import (
    OpenAITextEmbeddingResponse,
    OpenAITextEmbeddingResponseDataItem,
)


class OpenAITriton:
    """A Triton client that is OpenAI-embedding-api compatible and Cohere-rerank-api compatible"""

    def __init__(self, url: str, model_version: str = "1"):
        """Initialize an async Triton client

        Parameters
        ----------
        url : str
            e.g `localhost:8001`
        model_version : str, optional
            version of the model, by default "1"
        """
        self.url = url.strip("/")
        self.model_version = model_version

    def create_embedding(self, model: str, input: Union[str, List[str]]) -> OpenAITextEmbeddingResponse:
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
        triton_client = grpcclient.InferenceServerClient(url=self.url)
        input_text = []
        if isinstance(input, str):
            input_text.append(input)
        else:
            input_text = input
        if input_text:
            try:
                embedding_list = []
                for text in input_text:
                    raw_text = np.array([[text]], dtype=object)  # shape: [1, 1]
                    # Convert the text to a numpy array of type object (required for BYTES)
                    infer_input = grpcclient.InferInput("text", raw_text.shape, "BYTES")
                    infer_input.set_data_from_numpy(raw_text)

                    # Specify the requested output.
                    text_embeds = grpcclient.InferRequestedOutput("embeddings")

                    # Synchronous inference call.
                    response = triton_client.infer(model_name=model, inputs=[infer_input], outputs=[text_embeds])
                    embedding = OpenAITextEmbeddingResponseDataItem(
                        embedding=response.as_numpy("embeddings")[0].tolist()
                    )
                    # Extract the output embedding.

                    embedding_list.append(embedding)
                output = OpenAITextEmbeddingResponse(data=embedding_list, model=model)
                return output
            except Exception as e:
                traceback.print_exc()
                raise Exception(f"Error during inference: {str(e)}")
        else:
            raise ValueError("Input text must be a string or a list of strings.")

   
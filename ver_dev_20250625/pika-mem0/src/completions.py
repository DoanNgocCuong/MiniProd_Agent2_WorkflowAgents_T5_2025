import logging
import subprocess
import sys
import threading
from typing import List, Optional, Union

import httpx

import mem0
import json
import asyncio
try:
    import litellm
except ImportError:
    user_input = input("The 'litellm' library is required. Install it now? [y/N]: ")
    if user_input.lower() == "y":
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "litellm"])
            import litellm
        except subprocess.CalledProcessError:
            print("Failed to install 'litellm'. Please install it manually using 'pip install litellm'.")
            sys.exit(1)
    else:
        raise ImportError("The required 'litellm' library is not installed.")
        sys.exit(1)

from mem0.configs.prompts import MEMORY_ANSWER_PROMPT
from src.config import URL_PROFILE, TOKEN_PROFILE
import aiohttp
import logging, json, os, traceback
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from enum import Enum
from OpenAITriton.openai_triton import OpenAITriton
from src.config import LOCAL_MODEL_BASE_URL
from src.models import UserProfile

logger = logging.getLogger(__name__)

class MemoryMode(Enum):
    MILVUS_ONLY = "milvus_only"
    PROFILE_ONLY = "profile_only"
    HYBRID = "hybrid"

class Completions:
    def __init__(self, mem0_client):
        self.mem0_client = mem0_client
        self.embedder = OpenAITriton(url=LOCAL_MODEL_BASE_URL, model_version="1")
        self.memory_mode = MemoryMode.PROFILE_ONLY  # Default mode
        self.profile_similarity_threshold = 0.7  # Default threshold

    def set_memory_mode(self, mode: MemoryMode):
        """
        Set the memory mode for response generation
        """
        self.memory_mode = mode

    def embed_user_profile(self, profile: UserProfile) -> List[float]:
        """
        Embed user profile data by concatenating key-value pairs
        """
        # embedding each key-value pair in the profile separately
        embedding = None
        for key, value in profile.profile_data.items():
            if value:
                text = f"{key}: {value}"
                embedding = self.embedder.create_embedding(model="embedding", input=text).data[0].embedding
        return embedding

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
        # print(f"profiles: {profiles}")
        # Sort by similarity score and return top k
        if top_k > len(profiles):
            top_k = len(profiles)
        matched_profiles = sorted(profiles, key=lambda x: x.score, reverse=True)[:top_k]
        return matched_profiles


    async def call_api_get_user_profile(self, conversation_id: str) -> dict:
        """
        Fetch user profile from external service
        """
        try:
            url = f"{str(URL_PROFILE)}/user_profile"
            params = {
                "conversation_id": conversation_id,
                "token": TOKEN_PROFILE
            }
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    text = await response.text()
                    logging.info(f"====================={url} - {params} - {text}")
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == 200:
                            return data.get("data")
            return None
        except:
            logging.info(f"[ERROR] call_api_get_user_profile: {traceback.format_exc()}")
            return None

    def _construct_query(self, messages: List[dict]) -> str:
        """
        Construct query from messages using the same method as Milvus memory retrieval
        """
        message_input = []
        for message in messages:
            if message['role'] != 'system':
                message_input.append(f"{message['role']}: {message['content']}")
        # Use last 6 messages like in Milvus retrieval
        message_input = message_input[-6:]
        return "\n".join(message_input)

    def create(
        self,
        model: str,
        mode: str,
        messages: List = [],
        conversation_id: Optional[str] = None,
        # Mem0 arguments
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        filters: Optional[dict] = None,
        limit: Optional[int] = 10,
        threshold: Optional[float] = 0.01,
        # LLM arguments
        timeout: Optional[Union[float, str, httpx.Timeout]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stream: Optional[bool] = None,
        stream_options: Optional[dict] = None,
        stop=None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[dict] = None,
        user: Optional[str] = None,
        # openai v1.0+ new params
        response_format: Optional[dict] = None,
        seed: Optional[int] = None,
        tools: Optional[List] = None,
        tool_choice: Optional[Union[str, dict]] = None,
        logprobs: Optional[bool] = None,
        top_logprobs: Optional[int] = None,
        parallel_tool_calls: Optional[bool] = None,
        deployment_id=None,
        extra_headers: Optional[dict] = None,
        # soon to be deprecated params by OpenAI
        functions: Optional[List] = None,
        function_call: Optional[str] = None,
        # set api_base, api_version, api_key
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        api_key: Optional[str] = None,
        model_list: Optional[list] = None,  # pass in a list of api_base,keys, etc.
    ):
        if not any([user_id, agent_id, run_id]):
            raise ValueError("One of user_id, agent_id, run_id must be provided")

        if not litellm.supports_function_calling(model):
            raise ValueError(
                f"Model '{model}' does not support function calling. Please use a model that supports function calling."
            )

        # 1. Get user profile from API
        user_profile = None
        top_k_profiles = []
        if mode in [MemoryMode.PROFILE_ONLY, MemoryMode.HYBRID]:
            response_profile = asyncio.run(self.call_api_get_user_profile("e1ea0ecd-b4f3-4d39-810d-3f26d3f4b932_ebee7aa8-efd2-44af-bde0-01fd3d45c1d3"))
            # print(f"response_profile: {response_profile}")
            if response_profile:
                user_profile = []
                for key, value in response_profile.items():
                    if value:
                        user_profile.append(UserProfile(conversation_id=conversation_id, profile_data={str(key): str(value)}))
                # print(f"user_profile: {user_profile}")
                if user_profile and self.memory_mode == MemoryMode.PROFILE_ONLY:
                    # 2. Construct and embed query
                    query = self._construct_query(messages)                    
                    # 3. Calculate similarity score
                    top_k_profiles = self.match_user_profiles(query, user_profile, 5 )
                    # print(f"top_k_profiles: {top_k_profiles}")
                    for profile in top_k_profiles:
                        print(f"profile: {profile}")

        # Get previous messages except last message
        previous_messages = messages[:-1]
        conversations = []
        conversation_str = ""
        for message in previous_messages:
            conversation_str += f"{message['role']}: {message['content']}\n"
        conversations.append({
            "role": "user",
            "content": conversation_str
        })

        prepared_messages = self._prepare_messages(conversations)
        
        # Handle different memory modes
        if mode == MemoryMode.MILVUS_ONLY:
            # Use only Milvus memories
            relevant_memories = self._fetch_relevant_memories(messages, user_id, agent_id, run_id, filters, limit, threshold)
        elif mode == MemoryMode.PROFILE_ONLY:
            # Use only user profile
            relevant_memories = {"results": []}
            if top_k_profiles:
                profile_text = "\n".join([f"{key}: {value}" for profile in top_k_profiles for key, value in profile.profile_data.items()])
                relevant_memories["results"].append({
                    "memory": "User Profile Context: " + profile_text,
                    "score": 1.0
                })
        else:  # HYBRID mode
            # Use both Milvus and profile based on similarity
            relevant_memories = self._fetch_relevant_memories(messages, user_id, agent_id, run_id, filters, limit, threshold)
            if top_k_profiles and user_profile:
                profile_text = "\n".join([profile.profile_data for profile in top_k_profiles])
                relevant_memories["results"].append({
                    "memory": "User Profile Context: " + profile_text,
                    "score": top_k_profiles[0].score
                })

        prepared_messages[-1]["content"] = self._format_query_with_memories(messages, relevant_memories)
        print(f"prepared_messages: {json.dumps(prepared_messages, ensure_ascii=False, indent=4)}")
        response = litellm.completion(
            model=model,
            messages=prepared_messages,
            temperature=0.65,
            top_p=0.95,
            n=n,
            timeout=timeout,
            stream=stream,
            stream_options=stream_options,
            stop=stop,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logit_bias=logit_bias,
            user=user,
            response_format=response_format,
            seed=seed,
            tools=tools,
            tool_choice=tool_choice,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            parallel_tool_calls=parallel_tool_calls,
            deployment_id=deployment_id,
            extra_headers=extra_headers,
            functions=functions,
            function_call=function_call,
            base_url=base_url,
            api_version=api_version,
            api_key=api_key,
            model_list=model_list,
        )
        print(f"response: {response}")
        return response, relevant_memories

    def _prepare_messages(self, messages: List[dict]) -> List[dict]:
        if not messages or messages[0]["role"] != "system":
            print(f"MEMORY_ANSWER_PROMPT: {MEMORY_ANSWER_PROMPT}")
            return [{"role": "system", "content": MEMORY_ANSWER_PROMPT}] + messages
        return messages

    def _async_add_to_memory(self, messages, user_id, agent_id, run_id, metadata, filters):
        def add_task():
            logger.debug("Adding to memory asynchronously")
            self.mem0_client.add(
                messages=messages,
                user_id=user_id,
                agent_id=agent_id,
                run_id=run_id,
                metadata=metadata,
                filters=filters,
            )

        threading.Thread(target=add_task, daemon=True).start()

    def _fetch_relevant_memories(self, messages, user_id, agent_id, run_id, filters, limit, threshold):
        # Currently, only pass the last 6 messages to the search API to prevent long query
        message_input = []
        for message in messages:
            if message['role'] != 'system':
                message_input.append(f"{message['role']}: {message['content']}")
        message_input = message_input[-6:]
        # TODO: Make it better by summarizing the past conversation
        results = self.mem0_client.search(
            query="\n".join(message_input),
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            filters=filters,
            limit=limit,
        )
        
        
        relevant_memories = {
            "results": [],
        }           
        for result in results.get("results", []):
            if result.get("score", 0) >= threshold:
                relevant_memories["results"].append(result)
        return relevant_memories
        
    def _cosine_similarity(self, vec1, vec2):
        """Calculate cosine similarity between two vectors."""
        import numpy as np
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2)

    def _format_query_with_memories(self, messages, relevant_memories):
        # Check if self.mem0_client is an instance of Memory or MemoryClient
        entities = []
        print(f"messages: {messages}")
        memories_text = ""
        if relevant_memories.get("results"):
            memories_text = "\n".join(f"user fact {i}: " + memory["memory"] for i, memory in enumerate(relevant_memories["results"], 1))
        if relevant_memories.get("facts"):
            memories_text = "\n".join(f"fact {i}: " + memory["memory"] for i, memory in enumerate(relevant_memories["facts"], 1))
        if relevant_memories.get("relations"):
            entities = [entity for entity in relevant_memories["relations"]]
        situation_user = ""
        assistant_response = ""
        for message in messages[:-1]:
            situation_user += f"{message['role']}: {message['content']}\n"
        assistant_response += f"{messages[-1]['role']}: {messages[-1]['content']}\n"
        return f"- User Information Retrieved Memories/Facts: {memories_text} - Assistant's response: {assistant_response}\n\n - Situation Conversation User: {situation_user}"

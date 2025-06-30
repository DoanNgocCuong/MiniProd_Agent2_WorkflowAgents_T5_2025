import os
import asyncio
os.environ["OPENAI_API_KEY"] = "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"

from mem0 import Memory, AsyncMemory

config = {
    "vector_store": {
        "provider": "milvus",
        "config": {
            "collection_name": "mem0_facts",
            "embedding_model_dims": "1536",
            "url": "http://0.0.0.0:19530",
            "token": "root:Milvus",
        },
    },
    "version": "v1.1",
}

async def main():
    m = await AsyncMemory.from_config(config)
    messages = "conversation": [
    {"role": "user", "content": "I went to Ha Noi Yesterday, the food is deli"},
    {"role": "assistant", "content": "How about a thriller movies? They can be quite engaging."},
    {"role": "user", "content": "I'm not a big fan of thriller movies but I love sci-fi movies."},
    {"role": "assistant", "content": "Got it! I'\''ll avoid thriller recommendations and suggest sci-fi movies in the future."}
]
    result = await m.add(messages, user_id="hoailb1")
    print(result)
if __name__ == "__main__":
    asyncio.run(main())
    # print(m.get_all())

# print(m.search("I'm to play video games. Any recommendations?", user_id="hoailb1"))
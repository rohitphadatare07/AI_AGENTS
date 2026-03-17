import asyncio
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex
from llama_index.core import SimpleDirectoryReader
from llama_index.core import Document
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline
# from llama_index.llms.huggingface_api import HuggingFaceInferenceAPI
from llama_index.llms.ollama import Ollama
# from llama_index.core.evaluation import FaithfulnessEvaluator
from llama_index.core.tools import QueryEngineTool
from llama_index.core.agent.workflow import (
    AgentWorkflow,
    FunctionAgent,
    ReActAgent,
)

reader = SimpleDirectoryReader(input_dir="data")
documents = reader.load_data()

db = chromadb.PersistentClient(path="./agent_chroma_db")
chroma_collection = db.get_or_create_collection("ayurved_agent_collection")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

print("ingesting documents...")
# create the pipeline with transformations
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_overlap=0),
        HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5"),
    ],
    vector_store=vector_store,
)

# nodes = pipeline.run(documents=documents)   #run the pipeline to ingest documents and create nodes in the vector store
# print(nodes)

embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
print("querying index...")
llm = Ollama(
    model="qwen3.5:0.8b",
    temperature=0.7
)
query_engine = index.as_query_engine(
    llm=llm,
    response_mode="tree_summarize",
)

index_query_tool = QueryEngineTool.from_defaults(
    query_engine=query_engine,
    name="index_query_tool",
    description="Useful for answering questions about ayurvedic medicines and treatment. Input should be a question about symptoms, conditions, or treatments.",
    return_direct=False,
)

print("Collection count:", chroma_collection.count())

# retriever = index.as_retriever()
# docs = retriever.retrieve("What is line of treatment for Hypothyroidismis in ayurveda?")

# print("Retrieved docs:", len(docs))

# initialize agent
query_engine_agent = AgentWorkflow.from_tools_or_functions(
    [index_query_tool],
    llm=llm,
    system_prompt="You are a helpful assistant that has access to a database containing ayurvedic medicines and treatment information."
)
async def main():
    response = await query_engine_agent.run(
        "What is line of treatment for Hypothyroidismis in ayurveda?"
    )
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
# ayurved_medicine_query_tool = QueryEngineTool.from_defaults(
#     query_engine=query_engine,
#     name="ayurved_medicine_query_tool",
#     description="Useful for answering questions about ayurvedic medicines and treatment. Input should be a question about symptoms, conditions, or treatments.",
#     return_direct=False,
# )
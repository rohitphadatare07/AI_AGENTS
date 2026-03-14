from llama_index.core import SimpleDirectoryReader, Document
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.ingestion import IngestionPipeline


reader = SimpleDirectoryReader(input_dir="C:\\Users\\91810\\Downloads\\aws-amazon-emr-best-practices.pdf")
documents = reader.load_data()

sentence_transformer = OllamaEmbedding(
    model_name="qwen3-embedding:0.6b",
    base_url="http://localhost:11434",
)

# create the pipeline with transformations
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_overlap=0),
        OllamaEmbedding(model_name="BAAI/bge-small-en-v1.5"),
    ]
)

nodes = await pipeline.arun(documents=[Document.example()])
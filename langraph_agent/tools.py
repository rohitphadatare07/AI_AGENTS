from langchain_core.tools import Tool
from retriever import query_engine

def rag_query(query: str) -> str:
    response = query_engine.query(query)
    return str(response)

ayurved_medicine_query_tool = Tool(
    name="RAG Tool",
    func=rag_query,
    description="Useful for answering questions about ayurvedic medicines and treatment. Input should be a question about symptoms, conditions, or treatments.",
)
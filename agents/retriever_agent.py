from fastapi import FastAPI, HTTPException
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from config.settings import settings
import uvicorn
import os

app = FastAPI()
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=settings.GOOGLE_API_KEY)
vector_db_path = settings.VECTOR_DB_PATH

# Load or create FAISS index
def get_vector_store():
    if os.path.exists(vector_db_path):
        return FAISS.load_local(vector_db_path, embeddings, allow_dangerous_deserialization=True)
    return None

vector_store = get_vector_store()

@app.post("/retriever/add_documents/")
async def add_documents(documents: list[dict]):
    global vector_store
    langchain_docs = [Document(page_content=d["page_content"], metadata=d.get("metadata", {})) for d in documents]
    if vector_store:
        vector_store.add_documents(langchain_docs)
    else:
        vector_store = FAISS.from_documents(langchain_docs, embeddings)
    vector_store.save_local(vector_db_path)
    return {"status": "success", "message": f"Added {len(documents)} documents."}

@app.get("/retriever/retrieve_chunks/")
async def retrieve_chunks(query: str, top_k: int = settings.RETRIEVAL_TOP_K):
    if not vector_store:
        raise HTTPException(status_code=404, detail="Vector store not initialized. Add documents first.")
    try:
        docs = vector_store.similarity_search(query, k=top_k)
        return {"query": query, "chunks": [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in docs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # To run this agent: uvicorn agents.retriever_agent:app --host 0.0.0.0 --port 8003 --reload
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(settings.VECTOR_DB_PATH), exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=settings.RETRIEVER_AGENT_PORT)
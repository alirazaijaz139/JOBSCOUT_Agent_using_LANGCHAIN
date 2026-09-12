import os
import shutil
import sys

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document
from dotenv import load_dotenv

# Two directories need to be importable:
#   - the project root (JobScout-AI/) — so `Tools.job_search_tool` and
#     root-level `agent.py` resolve correctly.
#   - this file's own directory (jobscout_ai/) — so `RAG.loader` etc.
#     resolve correctly (RAG lives inside jobscout_ai/, not the root).
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)

sys.path.append(ROOT_DIR)
sys.path.append(CURRENT_DIR)

load_dotenv("jobscout_ai/.env")

from RAG.loader import split_text
from RAG.embeddings import get_embeddings
from RAG.vectorstore import create_vectorstore
from RAG.retrieval import get_retriever
from langchain_google_genai import ChatGoogleGenerativeAI

from Tools.job_search_tool import recommend_jobs_from_cv
from agent import run_agent

app = FastAPI(title="JobScout AI API")

# Allow the React dev server (and any frontend) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store per session is out of scope for a hackathon demo —
# we keep it simple with a single global "current CV" like the
# Streamlit version's st.session_state did.
STATE = {
    "cv_text": "",
    "retriever": None,
}


def extract_text(file: UploadFile, raw: bytes) -> str:

    if file.filename.endswith(".pdf"):

        import io
        reader = PdfReader(io.BytesIO(raw))

        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        return text

    elif file.filename.endswith(".docx"):

        import io
        document = Document(io.BytesIO(raw))

        text = ""
        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"

        return text

    return ""


@app.post("/api/upload-cv")
async def upload_cv(file: UploadFile = File(...)):

    raw = await file.read()
    text = extract_text(file, raw)

    if not text.strip():
        return {"error": "Could not extract text from this file."}

    STATE["cv_text"] = text

    chunks = split_text(text)
    embeddings = get_embeddings()
    vectorstore = create_vectorstore(chunks, embeddings)
    STATE["retriever"] = get_retriever(vectorstore)

    return {
        "cv_text": text,
        "num_chunks": len(chunks),
        "first_chunk": chunks[0].page_content if chunks else "",
    }


class AskRequest(BaseModel):
    question: str


@app.post("/api/ask-cv")
async def ask_cv(body: AskRequest):

    if not STATE["retriever"]:
        return {"error": "Upload a CV first."}

    docs = STATE["retriever"].invoke(body.question)

    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)

    context = "\n\n".join(doc.page_content for doc in docs)

    prompt = f"""
Answer the question using only the context below.

Context:
{context}

Question:
{body.question}
"""

    response = llm.invoke(prompt)

    if isinstance(response.content, list):
        answer = "\n".join(
            item.get("text", "")
            for item in response.content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    else:
        answer = response.content

    return {
        "answer": answer,
        "retrieved_chunks": [doc.page_content for doc in docs],
    }


class SearchRequest(BaseModel):
    question: str


@app.post("/api/search-jobs")
async def search_jobs_endpoint(body: SearchRequest):

    answer = run_agent(body.question, STATE["cv_text"])

    return {"answer": answer}


@app.post("/api/recommend-jobs")
async def recommend_jobs_endpoint():

    if not STATE["cv_text"]:
        return {"error": "Upload a CV first."}

    recommendations = recommend_jobs_from_cv.invoke(STATE["cv_text"])

    return {"recommendations": recommendations}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
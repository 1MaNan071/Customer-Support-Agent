"""
Customer Support Agent - FastAPI Backend
Vercel-compatible serverless API for the customer support chatbot.
"""

import json
import csv
import io
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from groq import Groq

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Customer Support Agent API",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# FAQ data store
# ---------------------------------------------------------------------------

FAQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "faq_data.json")

def _load_faqs_from_file() -> list:
    """Load FAQ data from the bundled JSON file."""
    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# Runtime FAQ store – initialised from the JSON file on cold-start.
# NOTE: On Vercel (serverless) any runtime additions are ephemeral. For
# persistent storage, connect a database (Supabase, PlanetScale, Vercel KV …).
_faq_store: list = _load_faqs_from_file()


def _get_faqs() -> list:
    return _faq_store

# ---------------------------------------------------------------------------
# Groq client helper
# ---------------------------------------------------------------------------

_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY environment variable is not set.",
        )
    return Groq(api_key=api_key)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[Message] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    classification: str


class FAQItem(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class FAQBulkUpload(BaseModel):
    faqs: List[FAQItem]

# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

CLASSIFICATION_SYSTEM_PROMPT = """You are a routing agent for a customer support assistant.
Classify the user's query into EXACTLY ONE of these categories and respond with ONLY the category name (nothing else):

- faq_retriever: Standard support questions about products, services, shipping, returns, accounts, billing, technical issues, etc.
- escalate_harmful: Queries containing personal identifiable information (SSN, credit card numbers, passwords), abuse, threats, hate speech, or security risks.
- escalate_off_topic: Completely off-topic queries unrelated to customer support (e.g., jokes, weather, general knowledge, recipes).

Respond with only one of: faq_retriever, escalate_harmful, escalate_off_topic"""


def _classify_input(client: Groq, message: str) -> str:
    """Classify user input into one of three routing categories."""
    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
            max_tokens=20,
        )
        result = resp.choices[0].message.content.strip().lower()
        if "harmful" in result:
            return "escalate_harmful"
        if "off_topic" in result:
            return "escalate_off_topic"
        return "faq_retriever"
    except Exception:
        # Default to FAQ if classification fails
        return "faq_retriever"

# ---------------------------------------------------------------------------
# FAQ answering logic
# ---------------------------------------------------------------------------

def _answer_from_faqs(client: Groq, message: str, history: List[Message]) -> str:
    """Build a prompt with the full FAQ knowledge-base and answer the user."""
    faqs = _get_faqs()

    if not faqs:
        return (
            "I don't have any knowledge-base data loaded yet. "
            "Please ask an administrator to upload FAQ data."
        )

    faq_context = "\n\n".join(
        f"Q: {faq['question']}\nA: {faq['answer']}" for faq in faqs
    )

    system_prompt = f"""You are a helpful, friendly, and professional customer support assistant.

RULES:
1. Answer the user's question using ONLY the knowledge base below.
2. Be concise and accurate. Use bullet points or numbered lists when helpful.
3. If the answer is NOT in the knowledge base, politely say you don't have that information and suggest they contact support directly.
4. Do NOT invent answers or provide information outside the knowledge base.
5. Maintain a warm and professional tone at all times.

--- KNOWLEDGE BASE ---
{faq_context}
--- END KNOWLEDGE BASE ---"""

    messages = [{"role": "system", "content": system_prompt}]

    # Include recent conversation history (up to last 10 turns)
    for msg in history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": message})

    resp = client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=600,
    )
    return resp.choices[0].message.content.strip()

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "faq_count": len(_get_faqs())}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Main chat endpoint – classifies and answers a user message."""
    client = _get_client()
    classification = _classify_input(client, request.message)

    if classification == "escalate_harmful":
        return ChatResponse(
            response=(
                "⚠️ I cannot process this request due to our safety policies. "
                "Please avoid sharing personal or sensitive information. "
                "How else can I help you?"
            ),
            classification=classification,
        )

    if classification == "escalate_off_topic":
        return ChatResponse(
            response=(
                "I'm a customer support assistant and can help with questions "
                "about our products and services. Could you please ask something "
                "related to our offerings?"
            ),
            classification=classification,
        )

    # faq_retriever path
    answer = _answer_from_faqs(client, request.message, request.history)
    return ChatResponse(response=answer, classification=classification)


# ── FAQ management endpoints ──────────────────────────────────────────────

@app.get("/api/faqs")
def get_faqs():
    """Return the current FAQ list."""
    return {"faqs": _get_faqs(), "count": len(_get_faqs())}


@app.post("/api/faqs")
def add_faqs(upload: FAQBulkUpload):
    """Add one or more FAQs to the knowledge base."""
    new_items = [item.model_dump() for item in upload.faqs]
    _faq_store.extend(new_items)
    return {"added": len(new_items), "total": len(_faq_store)}


@app.delete("/api/faqs/{index}")
def delete_faq(index: int):
    """Delete a single FAQ by its index."""
    if 0 <= index < len(_faq_store):
        removed = _faq_store.pop(index)
        return {"removed": removed, "total": len(_faq_store)}
    raise HTTPException(status_code=404, detail="FAQ index out of range.")


@app.delete("/api/faqs")
def clear_faqs():
    """Clear all FAQs from the knowledge base."""
    _faq_store.clear()
    return {"message": "All FAQs cleared.", "total": 0}


@app.post("/api/faqs/reset")
def reset_faqs():
    """Reset FAQs to the defaults from faq_data.json."""
    _faq_store.clear()
    _faq_store.extend(_load_faqs_from_file())
    return {"message": "FAQs reset to defaults.", "total": len(_faq_store)}


@app.post("/api/upload")
async def upload_faq_file(file: UploadFile = File(...)):
    """
    Upload a JSON or CSV file containing FAQs.

    **JSON format**: An array of objects with `question` and `answer` keys.
    **CSV format**: A CSV with `question` and `answer` column headers.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.")

    new_faqs: list = []
    filename_lower = file.filename.lower()

    if filename_lower.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file.")
        if not isinstance(data, list):
            raise HTTPException(
                status_code=400,
                detail="JSON must be an array of {question, answer} objects.",
            )
        for item in data:
            q = item.get("question", "").strip()
            a = item.get("answer", "").strip()
            if q and a:
                new_faqs.append({"question": q, "answer": a})

    elif filename_lower.endswith(".csv"):
        try:
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                q = row.get("question", "").strip()
                a = row.get("answer", "").strip()
                if q and a:
                    new_faqs.append({"question": q, "answer": a})
        except csv.Error:
            raise HTTPException(status_code=400, detail="Invalid CSV file.")

    elif filename_lower.endswith(".txt"):
        # Support simple TXT: each FAQ separated by a blank line.
        # Format:  Q: …\nA: …
        blocks = text.strip().split("\n\n")
        for block in blocks:
            lines = block.strip().split("\n")
            q_line = ""
            a_line = ""
            for line in lines:
                if line.lower().startswith("q:"):
                    q_line = line[2:].strip()
                elif line.lower().startswith("a:"):
                    a_line = line[2:].strip()
            if q_line and a_line:
                new_faqs.append({"question": q_line, "answer": a_line})
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload a .json, .csv, or .txt file.",
        )

    if not new_faqs:
        raise HTTPException(
            status_code=400,
            detail="No valid FAQ entries found in the uploaded file.",
        )

    _faq_store.extend(new_faqs)
    return {"added": len(new_faqs), "total": len(_faq_store), "faqs": _get_faqs()}


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


# ---------------------------------------------------------------------------
# Static file serving (local development – Vercel handles this via routes)
# ---------------------------------------------------------------------------

_PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")

if os.path.isdir(_PUBLIC_DIR):
    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(_PUBLIC_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=_PUBLIC_DIR), name="public")

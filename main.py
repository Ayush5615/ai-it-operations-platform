import os
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Literal

import jwt
import requests
import psycopg

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from pwdlib import PasswordHash


# ==================================================
# ENVIRONMENT CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

SECRET_KEY = os.getenv("SECRET_KEY")


# ==================================================
# OLLAMA CONFIGURATION
# ==================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"


# ==================================================
# KNOWLEDGE BASE CONFIGURATION
# ==================================================

KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"


# ==================================================
# FASTAPI APPLICATION
# ==================================================

app = FastAPI(
    title="AI IT Operations Platform",
    description="IT ticket management and AI-powered incident analysis platform",
    version="1.0.0"
)


# ==================================================
# CORS CONFIGURATION
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# PASSWORD + JWT CONFIGURATION
# ==================================================

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_connection():

    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ==================================================
# PYDANTIC MODELS
# ==================================================

class Ticket(BaseModel):

    title: str
    description: str
    priority: Literal["low", "medium", "high"]


class TicketStatusUpdate(BaseModel):

    status: Literal[
        "open",
        "in_progress",
        "resolved",
        "closed"
    ]


class UserCreate(BaseModel):

    username: str
    password: str


# ==================================================
# JWT TOKEN CREATION
# ==================================================

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = (
        datetime.now(timezone.utc)
        + timedelta(hours=1)
    )

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm="HS256"
    )

    return encoded_jwt


# ==================================================
# CURRENT USER
# ==================================================

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"]
        )

        username = payload.get("sub")

        if username is None:
            raise credentials_exception

        return {
            "username": username,
            "role": payload.get(
                "role",
                "support"
            )
        }

    except jwt.ExpiredSignatureError:

        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    except jwt.InvalidTokenError:

        raise credentials_exception


# ==================================================
# HOME
# ==================================================

@app.get("/")
def home():

    return {
        "message": "AI IT Operations Platform API is running"
    }


# ==================================================
# REGISTER
# ==================================================

@app.post(
    "/register",
    status_code=201
)
def register(user: UserCreate):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT id
                FROM users
                WHERE username = %s
                """,
                (user.username,)
            )

            existing_user = cur.fetchone()

            if existing_user:

                raise HTTPException(
                    status_code=409,
                    detail="Username already exists"
                )

            hashed_password = password_hash.hash(
                user.password
            )

            cur.execute(
                """
                INSERT INTO users
                (
                    username,
                    hashed_password
                )
                VALUES (%s, %s)
                RETURNING
                    id,
                    username,
                    role,
                    created_at
                """,
                (
                    user.username,
                    hashed_password
                )
            )

            new_user = cur.fetchone()

            conn.commit()

            return {
                "id": new_user[0],
                "username": new_user[1],
                "role": new_user[2],
                "created_at": new_user[3]
            }

    finally:

        conn.close()


# ==================================================
# LOGIN
# ==================================================

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    username,
                    hashed_password,
                    role
                FROM users
                WHERE username = %s
                """,
                (form_data.username,)
            )

            user = cur.fetchone()

            if not user:

                raise HTTPException(
                    status_code=401,
                    detail="Incorrect username or password",
                    headers={
                        "WWW-Authenticate": "Bearer"
                    }
                )

            password_valid = password_hash.verify(
                form_data.password,
                user[2]
            )

            if not password_valid:

                raise HTTPException(
                    status_code=401,
                    detail="Incorrect username or password",
                    headers={
                        "WWW-Authenticate": "Bearer"
                    }
                )

            access_token = create_access_token(
                {
                    "sub": user[1],
                    "role": user[3]
                }
            )

            return {
                "access_token": access_token,
                "token_type": "bearer"
            }

    finally:

        conn.close()


# ==================================================
# GET ALL TICKETS
# ==================================================

@app.get("/tickets")
def get_tickets(
    current_user: dict = Depends(
        get_current_user
    )
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    priority,
                    status,
                    created_at
                FROM tickets
                ORDER BY id
                """
            )

            rows = cur.fetchall()

            tickets = []

            for row in rows:

                tickets.append({
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "priority": row[3],
                    "status": row[4],
                    "created_at": row[5]
                })

            return tickets

    finally:

        conn.close()


# ==================================================
# GET SINGLE TICKET
# ==================================================

@app.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    current_user: dict = Depends(
        get_current_user
    )
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    priority,
                    status,
                    created_at
                FROM tickets
                WHERE id = %s
                """,
                (ticket_id,)
            )

            row = cur.fetchone()

            if not row:

                raise HTTPException(
                    status_code=404,
                    detail="Ticket not found"
                )

            return {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "priority": row[3],
                "status": row[4],
                "created_at": row[5]
            }

    finally:

        conn.close()


# ==================================================
# CREATE TICKET
# ==================================================

@app.post(
    "/tickets",
    status_code=201
)
def create_ticket(
    ticket: Ticket,
    current_user: dict = Depends(
        get_current_user
    )
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO tickets
                (
                    title,
                    description,
                    priority
                )
                VALUES (%s, %s, %s)
                RETURNING
                    id,
                    title,
                    description,
                    priority,
                    status,
                    created_at
                """,
                (
                    ticket.title,
                    ticket.description,
                    ticket.priority
                )
            )

            row = cur.fetchone()

            conn.commit()

            return {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "priority": row[3],
                "status": row[4],
                "created_at": row[5]
            }

    finally:

        conn.close()


# ==================================================
# UPDATE TICKET STATUS
# ==================================================

@app.put(
    "/tickets/{ticket_id}/status"
)
def update_ticket_status(
    ticket_id: int,
    status_update: TicketStatusUpdate,
    current_user: dict = Depends(
        get_current_user
    )
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE tickets
                SET status = %s
                WHERE id = %s
                RETURNING
                    id,
                    title,
                    description,
                    priority,
                    status,
                    created_at
                """,
                (
                    status_update.status,
                    ticket_id
                )
            )

            row = cur.fetchone()

            if not row:

                raise HTTPException(
                    status_code=404,
                    detail="Ticket not found"
                )

            conn.commit()

            return {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "priority": row[3],
                "status": row[4],
                "created_at": row[5]
            }

    finally:

        conn.close()


# ==================================================
# DELETE TICKET
# ==================================================

@app.delete(
    "/tickets/{ticket_id}"
)
def delete_ticket(
    ticket_id: int,
    current_user: dict = Depends(
        get_current_user
    )
):

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM tickets
                WHERE id = %s
                RETURNING id
                """,
                (ticket_id,)
            )

            row = cur.fetchone()

            if not row:

                raise HTTPException(
                    status_code=404,
                    detail="Ticket not found"
                )

            conn.commit()

            return {
                "message": "Ticket deleted successfully",
                "ticket_id": row[0]
            }

    finally:

        conn.close()


# ==================================================
# RAG - TEXT NORMALIZATION
# ==================================================

def normalize_text(text: str):

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ==================================================
# RAG - KNOWLEDGE RETRIEVAL
# ==================================================

def retrieve_knowledge(
    ticket_title: str,
    ticket_description: str
):

    query = normalize_text(
        f"{ticket_title} {ticket_description}"
    )

    query_words = set(
        query.split()
    )

    # ----------------------------------------------
    # Strong domain keywords
    # ----------------------------------------------

    vpn_keywords = {
        "vpn",
        "authentication",
        "credentials",
        "gateway",
        "remote",
        "dns",
        "firewall"
    }

    cpu_keywords = {
        "cpu",
        "processor",
        "usage",
        "load",
        "performance"
    }

    server_keywords = {
        "server",
        "service",
        "disk",
        "memory",
        "restart"
    }

    # ----------------------------------------------
    # Detect ticket domain
    # ----------------------------------------------

    vpn_match = any(
        keyword in query_words
        for keyword in vpn_keywords
    )

    cpu_match = any(
        keyword in query_words
        for keyword in cpu_keywords
    )

    server_match = any(
        keyword in query_words
        for keyword in server_keywords
    )

    # ----------------------------------------------
    # CPU gets priority over generic server terms
    # ----------------------------------------------

    if cpu_match:

        selected_domain = "cpu"

    elif vpn_match:

        selected_domain = "vpn"

    elif server_match:

        selected_domain = "server"

    else:

        # No clear supported domain
        return []

    documents = []

    if not KNOWLEDGE_BASE_DIR.exists():

        return []

    for file_path in KNOWLEDGE_BASE_DIR.glob(
        "*.txt"
    ):

        filename = file_path.name.lower()

        content = file_path.read_text(
            encoding="utf-8"
        )

        content_normalized = normalize_text(
            content
        )

        content_words = set(
            content_normalized.split()
        )

        score = len(
            query_words.intersection(
                content_words
            )
        )

        # ------------------------------------------
        # Strict domain matching
        # ------------------------------------------

        if selected_domain == "vpn":

            if "vpn" in filename:

                score += 100

            else:

                continue

        elif selected_domain == "cpu":

            if "cpu" in filename:

                score += 100

            else:

                continue

        elif selected_domain == "server":

            if (
                "server" in filename
                and "cpu" not in filename
                and "vpn" not in filename
            ):

                score += 100

            else:

                continue

        if score > 0:

            documents.append({
                "file": file_path.name,
                "content": content,
                "score": score
            })

    # ----------------------------------------------
    # Sort by relevance
    # ----------------------------------------------

    documents.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # ----------------------------------------------
    # Return strongest matching document only
    # ----------------------------------------------

    return documents[:1]


# ==================================================
# AI INCIDENT ANALYZER + RAG
# ==================================================

@app.post(
    "/tickets/{ticket_id}/analyze"
)
def analyze_ticket(
    ticket_id: int,
    current_user: dict = Depends(
        get_current_user
    )
):

    # ------------------------------------------------
    # GET TICKET
    # ------------------------------------------------

    conn = get_connection()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    priority,
                    status
                FROM tickets
                WHERE id = %s
                """,
                (ticket_id,)
            )

            ticket = cur.fetchone()

    finally:

        conn.close()

    if not ticket:

        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    # ------------------------------------------------
    # RETRIEVE KNOWLEDGE
    # ------------------------------------------------

    relevant_documents = retrieve_knowledge(
        ticket[1],
        ticket[2]
    )

    knowledge_context = ""

    for document in relevant_documents:

        knowledge_context += (
            f"\n\n--- KNOWLEDGE SOURCE: "
            f"{document['file']} ---\n"
            f"{document['content']}"
        )

    # ------------------------------------------------
    # AI PROMPT
    # ------------------------------------------------

    if relevant_documents:

        knowledge_instruction = f"""
INTERNAL KNOWLEDGE BASE:

{knowledge_context}
"""

    else:

        knowledge_instruction = """
INTERNAL KNOWLEDGE BASE:

No relevant internal knowledge-base document
was found for this ticket.
"""

    prompt = f"""
You are an IT Operations Support Engineer.

Your job is to analyze the incident using ONLY
the supplied internal knowledge base and ticket
information.

STRICT GROUNDING RULES:

1. Do not invent facts.
2. Do not invent KB article numbers.
3. Do not invent incident IDs.
4. Do not invent commands, policies, configurations,
   metrics, or system details.
5. Do not mention "KB Article 1234", "KB Article 5678",
   or any other article number unless that exact
   number exists in the supplied knowledge base.
6. If no relevant knowledge-base document is supplied,
   or if the knowledge base does not provide enough
   information, say:
   "Additional investigation is required."
7. Clearly distinguish between a probable cause and
   a possible contributing factor.
8. Use practical IT support language.
9. Keep the response concise.
10. Do not repeat the entire knowledge base.
11. Do not assume that a generic ticket belongs to
    a specific technical domain.
12. Do not use troubleshooting steps from an unrelated
    knowledge-base document.
13. If the ticket is unrelated to the supplied
    knowledge base, state that the available internal
    knowledge base does not contain a relevant
    troubleshooting procedure.

{knowledge_instruction}

TICKET:

Ticket ID: {ticket[0]}
Title: {ticket[1]}
Description: {ticket[2]}
Priority: {ticket[3]}
Status: {ticket[4]}

Return the analysis using exactly these sections:

Incident Analysis

Probable Root Cause

Possible Contributing Factors

Recommended Troubleshooting Steps

Recommended Resolution

Escalation Criteria

Next Steps

For troubleshooting steps, use only steps supported
by the relevant internal knowledge base.

For escalation criteria, use only escalation conditions
supported by the relevant internal knowledge base.

If no relevant knowledge base exists, do not invent
troubleshooting steps or escalation criteria.

Do not create fake references or article numbers.
"""


    # ------------------------------------------------
    # CALL OLLAMA
    # ------------------------------------------------

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            },
            timeout=120
        )

        response.raise_for_status()

        ai_result = response.json()

        analysis = ai_result.get(
            "response",
            ""
        ).strip()

        if not analysis:

            raise HTTPException(
                status_code=500,
                detail="AI model returned an empty response"
            )

        return {
            "ticket_id": ticket[0],
            "title": ticket[1],
            "priority": ticket[3],
            "analysis": analysis,
            "knowledge_sources": [
                document["file"]
                for document
                in relevant_documents
            ]
        }

    except requests.exceptions.ConnectionError:

        raise HTTPException(
            status_code=503,
            detail=(
                "Ollama is not running. "
                "Start Ollama and try again."
            )
        )

    except requests.exceptions.Timeout:

        raise HTTPException(
            status_code=504,
            detail="AI analysis request timed out."
        )

    except requests.exceptions.RequestException as e:

        raise HTTPException(
            status_code=500,
            detail=f"AI service error: {str(e)}"
        )
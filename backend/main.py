import os
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Literal

import jwt
import requests
import boto3
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

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/generate"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:3b"
)


# ==================================================
# KNOWLEDGE BASE CONFIGURATION
# ==================================================

KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"

AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_KNOWLEDGE_BASE_PREFIX = os.getenv(
    "S3_KNOWLEDGE_BASE_PREFIX",
    "knowledge_base/"
)

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION
)


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
    allow_headers=["*"]
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
# S3 KNOWLEDGE FILE READER
# ==================================================

def get_knowledge_file_from_s3(filename: str):

    response = s3_client.get_object(
        Bucket=S3_BUCKET_NAME,
        Key=f"{S3_KNOWLEDGE_BASE_PREFIX}{filename}"
    )

    return response["Body"].read().decode("utf-8")


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
    # DOMAIN KEYWORDS
    # ----------------------------------------------

    vpn_keywords = {
        "vpn",
        "vpnconnection",
        "gateway",
        "remoteaccess",
        "remote",
        "credentials",
        "authentication",
        "dns",
        "firewall",
        "antivirus"
    }

    cpu_keywords = {
        "cpu",
        "utilization",
        "processor",
        "load",
        "highcpu",
        "cpuusage"
    }

    server_keywords = {
        "server",
        "application",
        "service",
        "slow",
        "latency",
        "response",
        "timeout",
        "disk",
        "memory",
        "restart",
        "unavailable",
        "performance"
    }

    # ----------------------------------------------
    # DOMAIN DETECTION
    # ----------------------------------------------

    selected_domain = None

    # VPN gets highest priority
    if (
        "vpn" in query_words
        or query_words.intersection(vpn_keywords)
    ):

        selected_domain = "vpn"

    # Explicit CPU issue
    elif (
        query_words.intersection(cpu_keywords)
        or "high cpu" in query
        or "cpu usage" in query
        or "cpu utilization" in query
    ):

        selected_domain = "cpu"

    # Application/server performance issue
    elif (
        query_words.intersection(server_keywords)
    ):

        selected_domain = "server"

    # No supported domain
    else:

        return []

    # ----------------------------------------------
    # DOMAIN → EXACT KNOWLEDGE FILE
    # ----------------------------------------------

    domain_to_file = {

        "vpn":
            "vpn_troubleshooting.txt",

        "cpu":
            "cpu_incident_runbook.txt",

        "server":
            "server_troubleshooting.txt"
    }

    selected_file = domain_to_file.get(
        selected_domain
    )

    if not selected_file:

        return []

    # ----------------------------------------------
    # READ KNOWLEDGE FROM S3
    # ----------------------------------------------

    try:

        content = get_knowledge_file_from_s3(
            selected_file
        )

    except Exception:

        # ------------------------------------------
        # LOCAL FALLBACK
        # ------------------------------------------

        file_path = KNOWLEDGE_BASE_DIR / selected_file

        if not file_path.exists():

            return []

        content = file_path.read_text(
            encoding="utf-8"
        )

    # ----------------------------------------------
    # RETURN ONE BEST DOCUMENT ONLY
    # ----------------------------------------------

    return [
        {
            "file": selected_file,
            "content": content,
            "score": 100
        }
    ]


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
    # KNOWLEDGE INSTRUCTION
    # ------------------------------------------------

    if knowledge_context:

        knowledge_instruction = f"""
INTERNAL KNOWLEDGE BASE:
{knowledge_context}
"""

    else:

        knowledge_instruction = """
INTERNAL KNOWLEDGE BASE:

No relevant internal knowledge base document
was found for this ticket.
"""

    # ------------------------------------------------
    # AI PROMPT
    # ------------------------------------------------

    prompt = f"""
You are an IT Operations Support Engineer.

Analyze the incident using ONLY:

1. The ticket information.
2. The supplied internal knowledge base.

Do NOT use outside knowledge.

STRICT GROUNDING RULES:

1. Never invent facts.
2. Never invent root causes.
3. Never invent troubleshooting steps.
4. Never invent resolutions.
5. Never invent escalation criteria.
6. Never invent commands.
7. Never invent policies.
8. Never invent configurations.
9. Never invent metrics.
10. Never invent system details.
11. Never invent KB article numbers.
12. Never invent incident IDs.
13. Never create fake references.
14. Never mention "KB Article" anywhere in the response.
15. Never mention "Knowledge Base" as a citation or reference.
16. Never mention source filenames inside the analysis.
17. Never use general IT knowledge to fill missing information.
18. If the knowledge base does not support a statement,
    do not include that statement.

Do NOT add citations, references, article numbers,
source filenames, or parenthetical source explanations
to the answer.

ROOT CAUSE RULE:

Only provide a probable root cause if the supplied
knowledge base explicitly supports it for the reported issue.

Otherwise write exactly:

Additional investigation is required to determine the root cause.

CONTRIBUTING FACTOR RULE:

Only include contributing factors explicitly supported
by the supplied knowledge base.

Do not explain where the contributing factors came from.

TROUBLESHOOTING RULE:

Every troubleshooting step must be directly supported
by the supplied knowledge base.

Do not create additional steps.

Do not add source references to the steps.

RESOLUTION RULE:

Only provide a recommended resolution if it is explicitly
supported by the supplied knowledge base.

If the knowledge base does not explicitly support a resolution,
write exactly:

Additional investigation is required.

Do NOT add a "however" section or alternative suggestions.

ESCALATION RULE:

Only include escalation criteria explicitly stated
in the supplied knowledge base.

If escalation criteria are not supported, write:

Additional investigation is required.

KNOWLEDGE SOURCE RULE:

Use only the supplied knowledge source.

Do not combine information from documents that were not supplied.

If no relevant knowledge base document is supplied,
do not invent troubleshooting information.

In that case, clearly state that no relevant internal
knowledge base source was found.

Keep the response concise and practical.
IMPORTANT:
Do not repeat all possible causes or all troubleshooting steps from the knowledge base.
Select only the most relevant items for the specific ticket.
Return a maximum of 5 contributing factors, 5 troubleshooting steps, and 5 escalation criteria.
Do not add any step that is not explicitly present in the supplied knowledge base.

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

FINAL CHECK:

Before returning the response, verify that:

- No KB Article references are present.
- No Knowledge Base citations are present.
- No source filenames are present inside the analysis.
- No invented article numbers are present.
- No invented incident IDs are present.
- Every troubleshooting step comes from the supplied knowledge base.
- Every resolution statement comes from the supplied knowledge base.
- Every escalation condition comes from the supplied knowledge base.
- No outside IT knowledge has been added.
- No citations or parenthetical source references have been added.
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
                    "temperature": 0.0
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

        # ------------------------------------------------
        # REMOVE KNOWLEDGE BASE REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(Knowledge Base:\s*[^)]*\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        analysis = re.sub(
            r"\s*\[Knowledge Base:\s*[^\]]*\]",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE KB ARTICLE REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(KB Article:\s*\d+\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        analysis = re.sub(
            r"\s*\[KB Article:\s*\d+\]",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        analysis = re.sub(
            r"\s*KB Article:\s*\d+",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE ARTICLE REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(Article\s*#?\s*\d+\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        analysis = re.sub(
            r"\s*\[Article\s*#?\s*\d+\]",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE SOURCE FILENAMES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(?(?:Knowledge Base|Source|File)\s*:\s*[\w.-]+\.txt[^)]*\)?",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE ISSUE REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(Issue:\s*[^)]*\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE POSSIBLE CAUSE REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(Possible Cause:\s*[^)]*\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE TROUBLESHOOTING STEP REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\(Troubleshooting Step:\s*[^)]*\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # REMOVE PARENTHETICAL TXT REFERENCES
        # ------------------------------------------------

        analysis = re.sub(
            r"\s*\([^)]*\.txt[^)]*\)",
            "",
            analysis,
            flags=re.IGNORECASE
        )

        # ------------------------------------------------
        # CLEAN EXTRA SPACES
        # ------------------------------------------------

        analysis = re.sub(
            r"[ \t]{2,}",
            " ",
            analysis
        )

        analysis = re.sub(
            r"\n{3,}",
            "\n\n",
            analysis
        )

        analysis = analysis.strip()

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
                for document in relevant_documents
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
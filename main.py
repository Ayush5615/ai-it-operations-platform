from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import psycopg
from dotenv import load_dotenv
import os
from typing import Literal
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash


# --------------------------------------------------
# Environment Configuration
# --------------------------------------------------

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not configured in .env")


# --------------------------------------------------
# Password Hashing
# --------------------------------------------------

password_hash = PasswordHash.recommended()


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(
    title="AI IT Operations Platform",
    description="Backend API for IT incident and operations management",
    version="1.0.0"
)


# --------------------------------------------------
# Authentication Configuration
# --------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# --------------------------------------------------
# JWT Token Creation
# --------------------------------------------------

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(hours=1)

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm="HS256"
    )

    return encoded_jwt


# --------------------------------------------------
# Database Connection
# --------------------------------------------------

def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


# --------------------------------------------------
# Pydantic Models
# --------------------------------------------------

class Ticket(BaseModel):
    title: str
    description: str
    priority: Literal["low", "medium", "high"]


class TicketStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]


class UserCreate(BaseModel):
    username: str
    password: str


# --------------------------------------------------
# Home Endpoint
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "AI IT Operations Platform is running"
    }


# --------------------------------------------------
# User Registration
# --------------------------------------------------

@app.post("/register")
def register_user(user: UserCreate):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Check whether username already exists
        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE username = %s;
            """,
            (user.username,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Username already exists"
            )

        # Hash password before storing it
        hashed_password = password_hash.hash(user.password)

        cursor.execute(
            """
            INSERT INTO users
            (username, hashed_password)
            VALUES (%s, %s)
            RETURNING id, username, role, created_at;
            """,
            (
                user.username,
                hashed_password
            )
        )

        new_user = cursor.fetchone()

        conn.commit()

        return {
            "message": "User registered successfully",
            "user": {
                "id": new_user[0],
                "username": new_user[1],
                "role": new_user[2],
                "created_at": new_user[3]
            }
        }

    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------
# User Login
# --------------------------------------------------

@app.post("/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, username, hashed_password, role
            FROM users
            WHERE username = %s;
            """,
            (form_data.username,)
        )

        user = cursor.fetchone()

    finally:
        cursor.close()
        conn.close()

    # Username does not exist
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Verify password
    if not password_hash.verify(
        form_data.password,
        user[2]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Create JWT
    access_token = create_access_token(
        data={
            "sub": user[1],
            "role": user[3]
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# --------------------------------------------------
# Get Current User from JWT
# --------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=["HS256"]
        )

        username = payload.get("sub")
        role = payload.get("role")

        if username is None:
            raise credentials_exception

        return {
            "username": username,
            "role": role
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    except jwt.InvalidTokenError:
        raise credentials_exception


# --------------------------------------------------
# Create Ticket
# --------------------------------------------------

@app.post("/tickets", status_code=201)
def create_ticket(
    ticket: Ticket,
    current_user: dict = Depends(get_current_user)
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO tickets
            (title, description, priority)
            VALUES (%s, %s, %s)
            RETURNING id, title, description, priority, status, created_at;
            """,
            (
                ticket.title,
                ticket.description,
                ticket.priority
            )
        )

        new_ticket = cursor.fetchone()

        conn.commit()

        return {
            "message": "Ticket created successfully",
            "ticket": {
                "id": new_ticket[0],
                "title": new_ticket[1],
                "description": new_ticket[2],
                "priority": new_ticket[3],
                "status": new_ticket[4],
                "created_at": new_ticket[5]
            }
        }

    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------
# Get All Tickets
# --------------------------------------------------

@app.get("/tickets")
def get_tickets(
    current_user: dict = Depends(get_current_user)
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                priority,
                status,
                created_at
            FROM tickets
            ORDER BY id;
            """
        )

        rows = cursor.fetchall()

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

        return {
            "tickets": tickets
        }

    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------
# Get Single Ticket
# --------------------------------------------------

@app.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int,
    current_user: dict = Depends(get_current_user)
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                priority,
                status,
                created_at
            FROM tickets
            WHERE id = %s;
            """,
            (ticket_id,)
        )

        ticket = cursor.fetchone()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found"
            )

        return {
            "ticket": {
                "id": ticket[0],
                "title": ticket[1],
                "description": ticket[2],
                "priority": ticket[3],
                "status": ticket[4],
                "created_at": ticket[5]
            }
        }

    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------
# Update Ticket Status
# --------------------------------------------------

@app.put("/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    status_update: TicketStatusUpdate,
    current_user: dict = Depends(get_current_user)
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
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
                created_at;
            """,
            (
                status_update.status,
                ticket_id
            )
        )

        updated_ticket = cursor.fetchone()

        if not updated_ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found"
            )

        conn.commit()

        return {
            "message": "Ticket status updated successfully",
            "ticket": {
                "id": updated_ticket[0],
                "title": updated_ticket[1],
                "description": updated_ticket[2],
                "priority": updated_ticket[3],
                "status": updated_ticket[4],
                "created_at": updated_ticket[5]
            }
        }

    finally:
        cursor.close()
        conn.close()


# --------------------------------------------------
# Delete Ticket
# --------------------------------------------------

@app.delete("/tickets/{ticket_id}")
def delete_ticket(
    ticket_id: int,
    current_user: dict = Depends(get_current_user)
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM tickets
            WHERE id = %s
            RETURNING id;
            """,
            (ticket_id,)
        )

        deleted_ticket = cursor.fetchone()

        if not deleted_ticket:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found"
            )

        conn.commit()

        return {
            "message": "Ticket deleted successfully"
        }

    finally:
        cursor.close()
        conn.close()
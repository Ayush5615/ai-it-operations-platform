from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg
from dotenv import load_dotenv
import os
from typing import Literal

load_dotenv()

app = FastAPI()


class Ticket(BaseModel):
    title: str
    description: str
    priority: Literal["low", "medium", "high"]

def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


@app.get("/")
def home():
    return {"message": "AI IT Operations Platform is running"}


@app.post("/tickets", status_code=201)
def create_ticket(ticket: Ticket):
    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO tickets (title, description, priority)
        VALUES (%s, %s, %s)
        RETURNING id, title, description, priority, status, created_at;
        """,
        (ticket.title, ticket.description, ticket.priority)
    )

    new_ticket = cursor.fetchone()

    conn.commit()
    cursor.close()
    conn.close()

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
@app.get("/tickets")
def get_tickets():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, description, priority, status, created_at FROM tickets ORDER BY id;"
    )

    tickets = cursor.fetchall()

    cursor.close()
    conn.close()

    return {"tickets": tickets}

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, description, priority, status, created_at FROM tickets WHERE id = %s;",
        (ticket_id,)
    )

    ticket = cursor.fetchone()

    cursor.close()
    conn.close()

    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
        "id": ticket[0],
        "title": ticket[1],
        "description": ticket[2],
        "priority": ticket[3],
        "status": ticket[4],
        "created_at": ticket[5]
    }

class TicketStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]


@app.put("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: int, ticket_update: TicketStatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE tickets
        SET status = %s
        WHERE id = %s
        RETURNING id, title, description, priority, status, created_at;
        """,
        (ticket_update.status, ticket_id)
    )

    updated_ticket = cursor.fetchone()

    conn.commit()
    cursor.close()
    conn.close()

    if updated_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

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




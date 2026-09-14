\# AI-Powered IT Operations \& Incident Resolution Platform



An AI-powered IT operations platform that helps support teams manage IT incidents, retrieve relevant troubleshooting knowledge, and generate structured AI-based incident analysis and resolution recommendations.



\## Overview



The platform combines a ticket management system with Retrieval-Augmented Generation (RAG) to assist support engineers in troubleshooting IT incidents.



When a support ticket is analyzed, the system retrieves relevant troubleshooting information from a knowledge base stored in Amazon S3 and provides that context to Gemini for generating structured incident analysis and recommendations.



\## Key Features



\- User registration and JWT-based authentication

\- IT incident/ticket creation and management

\- Ticket priority and status management

\- AI-powered incident analysis

\- Retrieval-Augmented Generation (RAG)

\- Knowledge base retrieval from Amazon S3

\- Gemini-powered troubleshooting recommendations

\- Knowledge source visibility for AI responses

\- REST API built with FastAPI

\- PostgreSQL database for persistent ticket and user data

\- Dockerized backend deployment

\- React-based web interface

\- Nginx reverse proxy and frontend serving

\- AWS EC2 production deployment



\## AI \& RAG Workflow



Support Ticket → FastAPI → Retrieve Relevant Knowledge → Amazon S3 Knowledge Base → Relevant Troubleshooting Context → Gemini → Structured Incident Analysis → Troubleshooting \& Resolution Recommendations



The generated response includes the knowledge sources used during analysis, providing transparency about the troubleshooting information supplied to the AI model.



\## Architecture



User Browser → Nginx → React Frontend → FastAPI Backend → PostgreSQL + Amazon S3 → Gemini



\## Technology Stack



\*\*Frontend:\*\* React, JavaScript, HTML, CSS, Vite



\*\*Backend:\*\* Python, FastAPI, Uvicorn, REST APIs



\*\*Database:\*\* PostgreSQL, Psycopg



\*\*AI:\*\* Google Gemini API, RAG



\*\*Cloud \& Infrastructure:\*\* Amazon EC2, Amazon S3, AWS IAM, Docker, Nginx



\*\*Development Tools:\*\* Git, GitHub



\## Knowledge Base



\- `vpn\_troubleshooting.txt`

\- `cpu\_incident\_runbook.txt`

\- `server\_troubleshooting.txt`



Knowledge documents are stored in Amazon S3 and retrieved for relevant incidents.



\## Example AI Analysis



\*\*Incident:\*\* VPN not connecting



\*\*Priority:\*\* High



\*\*Knowledge Source:\*\* `vpn\_troubleshooting.txt`



The AI analyzes the incident using the relevant troubleshooting knowledge retrieved from the knowledge base and generates structured troubleshooting and resolution recommendations.



\## Project Structure



```text

ai-it-operations-platform/

├── backend/

│   ├── main.py

│   ├── requirements.txt

│   └── Dockerfile

├── frontend/

│   ├── src/

│   ├── package.json

│   └── vite.config.js

├── knowledge\_base/

│   ├── cpu\_incident\_runbook.txt

│   ├── server\_troubleshooting.txt

│   └── vpn\_troubleshooting.txt

└── .gitignore


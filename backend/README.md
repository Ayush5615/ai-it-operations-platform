\# AI-Powered IT Operations \& Incident Resolution Platform



A backend platform for managing IT support incidents through REST APIs, PostgreSQL, and automated ticket workflows.



\## Features



\- Create IT support tickets

\- Store tickets in PostgreSQL

\- Retrieve all tickets

\- Retrieve a ticket by ID

\- Update ticket status

\- Validate ticket status

\- Return proper HTTP errors for missing tickets

\- Environment-based database configuration



\## Tech Stack



\- Python

\- FastAPI

\- PostgreSQL

\- psycopg2

\- Pydantic

\- REST APIs

\- Git \& GitHub



\## API Endpoints



| Method | Endpoint | Description |

|---|---|---|

| GET | `/` | Health check |

| POST | `/tickets` | Create a ticket |

| GET | `/tickets` | Get all tickets |

| GET | `/tickets/{ticket\_id}` | Get ticket by ID |

| PUT | `/tickets/{ticket\_id}/status` | Update ticket status |



\## Current Architecture



Client → FastAPI REST API → PostgreSQL Database



\## Future Enhancements



\- AI-based ticket classification

\- Knowledge Base and RAG

\- Automated incident recommendations

\- Authentication and role-based access

\- Docker containerization

\- AWS deployment

\- Monitoring and logging



\## Project Status



Backend MVP completed with PostgreSQL database integration and REST API ticket management.


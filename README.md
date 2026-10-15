# TriageDesk

A four-service Docker Compose stack with a FastAPI health endpoint, PostgreSQL, a Northwind mock API, and a Next.js status dashboard.

## Run

Requirements: Docker Desktop with Docker Compose.

Set one environment variable and start the stack:

```bash
export POSTGRES_PASSWORD='change-this-password'
docker compose up --build

Open http://localhost:3000. The dashboard checks /healthz every five seconds and displays the API/database status.
Services
- web — Next.js dashboard, port 3000
- api — FastAPI health endpoint, port 8000
- db — PostgreSQL 16
- northwind — mock customer API, port 8001
All published ports bind to localhost.
Health check
GET /healthz executes SELECT 1 against PostgreSQL. It returns HTTP 200 when the database is reachable and HTTP 503 when it is unavailable. The response includes the service status, database status, and version.
Northwind mock
GET /accounts/{id} returns a mock account. Approximately 20% of requests return HTTP 429 with a Retry-After header.
Stop
docker compose down

To remove the database volume as well:
docker compose down -v
Dynamic Product Catalog Filter

Overview
- Flask backend that generates demo product data, persists it in SQLite, and exposes retrieval and search APIs.
- Lightweight HTML page (served at `/`) to seed sample data and exercise the search flow without an external frontend.
- Automated pytest to verify generation, pagination, and search behavior end to end.

Getting Started
- Install dependencies: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Launch server: `python app.py` (defaults to port 5050 if `FLASK_RUN_PORT` is unset)
- Health check: `GET http://localhost:5050/health`
- Demo UI: browse to `http://localhost:5050/`

API Endpoints
- `POST /products/generate` → body `{ "count": 100, "seed": 123 }` seeds demo products (count default 100; optional seed for deterministic data)
- `GET /products?page=1&limit=50` → paginated list sorted by `id`
- `GET /products/search?q=term&page=1&limit=50` → case-insensitive substring search across `name`, `description`, `category`, `brand`, and `sku`

Testing
- Activate the venv and run `pytest -q`

Improvement Ideas
- Swap SQLite for Postgres or add SQLite FTS5 indexes to support larger datasets and faster lookups.
- Introduce rate limiting and input validation (e.g., max page size, allowed characters) to harden the API.
- Expand UI with pagination controls, loading indicators, and richer filters (category, price range, brand).
- Containerize the service (Dockerfile + docker-compose) for reproducible deployment.
- Add CI workflow and broader test coverage (error cases, large dataset performance).

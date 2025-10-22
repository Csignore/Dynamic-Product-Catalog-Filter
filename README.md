Dynamic Product Catalog Filter - Flask Backend

Run locally
- Create venv and install: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Start server: `python app.py`
- Health check: `GET http://localhost:5000/health`
- Simple UI: open `http://localhost:5000/` to load the built-in test page

API
- `POST /products/generate` body: `{ "count": 100, "seed": 123 }` creates demo data
- `GET /products?page=1&limit=50` paginated list
- `GET /products/search?q=term&page=1&limit=50` case-insensitive substring search across name, description, category, brand, sku

Testing
- `pytest -q`

Notes
- Uses SQLite file `products.db` for local dev; in tests uses in-memory DB.
- Indexing: for larger datasets, add indexes on `name`, `brand`, `category`, and `sku` or switch to FTS (SQLite FTS5) / Postgres `GIN` on `tsvector`.

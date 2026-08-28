# Warp Policy Assignment System

## Run locally

Install/sync dependencies with uv:

```bash
uv sync
```

Start the FastAPI development server:

```bash
uv run fastapi dev main.py
```

Then open <http://127.0.0.1:8000> or the interactive API docs at
<http://127.0.0.1:8000/docs>.

## Endpoints

- `GET /` — health check
- `GET /items/{item_id}?q=...` — returns an item ID and optional query

# API.md — Endpoint Reference

Marketing Command Center | FastAPI Backend

> This file is updated as endpoints are built. For full OpenAPI spec, see `/docs` on the running backend.

---

## Base URL

`NEXT_PUBLIC_API_URL` (Railway deployment)

---

## Endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Per-source pipeline status, post counts, DB connectivity |

### Query

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/query/keyword` | Keyword (full-text) search |
| POST | `/api/query/semantic` | Semantic (RAG) search |
| POST | `/api/query/compare` | Side-by-side: both pipelines in parallel |

### Query History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/query/history` | Paginated list of past queries |
| GET | `/api/query/history/{id}` | Full saved results for a query |
| GET | `/api/query/history/{id}/export` | Download result set as .md file |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | Latest update per project |
| GET | `/api/projects/{name}/history` | All updates for a project |

### Mentions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mentions` | Paginated feed of brand mentions (is_mention=true posts). Params: `platform` (x\|linkedin\|all), `days` (int, default 7), `page`, `page_size` |

### Popular Posts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/popular` | Paginated feed of high-engagement posts. Params: `platform` (x\|slack\|all), `days` (int, default 30), `page`, `page_size` |

### Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | Total posts, ingestion health, active project count, popular post counts |

---

## Request / Response schemas

_(To be documented as endpoints are built — or generated via FastAPI's `/docs` OpenAPI UI)_

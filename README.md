# PaperMind AI 🧠

> RAG system for AI/ML research papers — upload PDFs, search semantically, and get grounded answers with exact citations.

## Architecture

```
PDF Upload → SHA-256 dedup → Text extract (PyMuPDF) → Metadata extraction → Chunking (512tok/64overlap)
→ Embeddings (MiniLM) → Postgres (BM25 FTS) + ChromaDB (vectors)
→ Hybrid retrieval (BM25 + semantic + RRF) → CrossEncoder reranking → LLM QA with citations
```

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 (SQLAlchemy async) |
| Vectors | ChromaDB (cosine, HNSW) |
| Queue | Celery + Redis 7 |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | OpenAI GPT-4o-mini (default) or Gemini 1.5 Flash |
| Frontend | React 18 + Vite |
| Auth | JWT (python-jose) + bcrypt |

## Quick Start

### 1. Configure environment

```bash
cd papermind-ai
cp .env.example .env
# Edit .env: set OPENAI_API_KEY (or GEMINI_API_KEY + LLM_PROVIDER=gemini)
```

### 2. Start all services

```bash
docker-compose up -d
```

This starts: PostgreSQL → Redis → ChromaDB → FastAPI (auto-runs Alembic migrations) → Celery worker

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 4. First steps
1. **Register** an account at `/auth`
2. **Upload** PDFs on the Upload page — they'll be processed in the background
3. **Search** once a paper is `ready`
4. **Ask AI** for grounded answers with citations

## API Reference

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT tokens |
| GET  | `/auth/me` | Current user |
| POST | `/papers` | Upload PDF (multipart) |
| GET  | `/papers` | List all papers |
| GET  | `/papers/{id}` | Paper detail |
| GET  | `/papers/{id}/status` | Processing status |
| PATCH| `/papers/{id}` | Update metadata |
| DELETE | `/papers/{id}` | Delete paper |
| GET  | `/papers/{id}/related` | Related papers |
| POST | `/search` | Search (keyword/semantic/hybrid) |
| POST | `/qa` | Grounded Q&A with citations |
| GET  | `/analytics/overview` | Dashboard stats |
| GET  | `/users/me/history` | Query history |

## LLM Provider

Switch between OpenAI and Gemini in `.env`:

```env
# Option A — OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Option B — Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

## Project Structure

```
papermind-ai/
├── app/
│   ├── api/v1/          ← API routers (auth, papers, search, qa, analytics, users)
│   ├── core/            ← config, security, logging
│   ├── db/              ← SQLAlchemy session, ChromaDB wrapper
│   ├── models/          ← ORM models (5 tables)
│   ├── providers/       ← LLM (OpenAI/Gemini), storage
│   ├── schemas/         ← Pydantic request/response
│   ├── services/        ← ingestion, chunker, embeddings, retrieval, reranker, QA, analytics
│   ├── workers/         ← Celery app + tasks
│   └── main.py          ← FastAPI factory
├── alembic/             ← DB migrations
├── docker/Dockerfile
├── frontend/src/
│   ├── screens/         ← Auth, Upload, Library, Search, QA, Analytics, History
│   ├── utils/api.js     ← API client
│   └── App.jsx          ← Router + sidebar
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

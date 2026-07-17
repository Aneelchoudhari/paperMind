# 🧠 PaperMind AI

**A Retrieval-Augmented Generation (RAG) system for AI/ML research papers.**

Upload PDF research papers, search across your library with keyword, semantic, or hybrid search, and ask natural-language questions that get answered strictly from your papers — with page-level, auditable citations.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-unlicensed-lightgrey.svg)](#license)

---

## Table of Contents

- [Overview](#overview)
- [Why RAG?](#why-rag)
- [Architecture](#architecture)
  - [Ingestion Pipeline](#ingestion-pipeline-write-path)
  - [Retrieval & QA Pipeline](#retrieval--qa-pipeline-read-path)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Retrieval Strategy — Hybrid Search](#retrieval-strategy--hybrid-search)
- [Grounded QA & Citation Enforcement](#grounded-qa--citation-enforcement)
- [Authentication & Security](#authentication--security)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
- [Known Limitations](#known-limitations--roadmap)
- [Glossary](#glossary)
- [License](#license)

---

## Overview

PaperMind AI lets a user upload PDF research papers (arXiv-style papers — think *"Attention Is All You Need"*) and:

- **Search** across all uploaded papers using keyword, semantic (meaning-based), or hybrid search.
- **Ask natural-language questions** and get answers grounded strictly in the uploaded papers, with exact citations (paper name, page number, section) attached to every claim.
- **View analytics** — paper counts, category/year breakdowns, top authors, and search history.

In one sentence: it's a personal, citation-backed research assistant built on **Retrieval-Augmented Generation (RAG)**.

## Why RAG?

Large Language Models are fluent but have two weaknesses:

- **Hallucination** — an LLM will confidently invent facts or citations because it's predicting the next likely token, not looking anything up.
- **Stale/limited knowledge** — an LLM only knows what was in its training data; it has never seen the PDF you just uploaded.

RAG fixes both: instead of asking the LLM to answer from memory, the system first **retrieves** the most relevant snippets from a private knowledge base (your uploaded papers), then hands the LLM only those snippets with the instruction *"answer using ONLY this text, and cite where each fact came from."*

---

## Architecture

There are **two independent pipelines**, and understanding they're separate is the key mental model.

### Ingestion Pipeline (write path)

Runs once per uploaded PDF, in the background.

```
1. User uploads a PDF via the React frontend
     │
2. FastAPI /papers endpoint:
     - checks it's really a PDF (magic bytes check)
     - checks size < 50MB
     - computes SHA-256 hash → rejects if this exact file was uploaded before (dedup)
     - saves the raw file to local disk storage
     - inserts a `papers` row with status = 'processing'
     - enqueues a Celery task and returns 202 Accepted IMMEDIATELY
     ▼
3. Celery worker (separate process) picks up the task:
     Step 2 — Extract text from every page (PyMuPDF)
     Step 3 — Extract metadata: title, authors, abstract, year, DOI, keywords
              (regex/font-size heuristics, LLM fallback if those fail)
     Step 4 — Chunk the text into ~512-token overlapping windows,
              sentence-aware, tagged with page number + section heading
     Step 5 — Generate a 384-dim embedding vector for every chunk
              (all-MiniLM-L6-v2 sentence-transformer model)
     Step 6 — Persist:
              (a) chunk rows      → Postgres `chunks` table
              (b) chunk vectors   → ChromaDB collection
              (c) paper row status → 'ready'
     │
4. Frontend polls GET /papers/{id}/status every 3s until status = 'ready'
```

### Retrieval & QA Pipeline (read path)

Runs every time a user searches or asks a question — reads only from what ingestion already built.

```
1. User asks: "How does self-attention reduce sequential computation?"
     │
2. POST /qa (JWT-authenticated)
     │
3. Hybrid retrieval:
     (a) Keyword search  — Postgres full-text search (BM25-like ts_rank_cd), top 50
     (b) Semantic search — embed the query, cosine similarity in ChromaDB, top 50
     (c) Reciprocal Rank Fusion (RRF) merges both lists → top 20
     │
4. Cross-encoder reranking (ms-marco-MiniLM-L-6-v2) re-scores the 20
   candidates against the literal question → top 5
     │
5. Prompt construction: the 5 winning chunks are numbered with paper
   title, page, and section, and inserted into a strict system prompt
     │
6. LLM call (gpt-4o-mini by default, swappable), forced into JSON mode
   → { answer, citations[], sufficient_evidence }
     │
7. Server-side citation validation — does NOT trust the LLM blindly:
     - sufficient_evidence == false  → replace with fixed fallback sentence
     - cited chunk_id not in the 5 sent → reject the ENTIRE answer
     - [n] marker with no matching citation entry → strip the marker
     │
8. Persist to `search_history` + `qa_citations`, return to frontend
     │
9. Frontend renders [1][2][3] superscripts + a "Sources" panel
```

**Why the split matters:** Ingestion is slow (seconds to minutes) and only needs to happen once, so it's pushed to a background worker and the API responds instantly (`202 Accepted`). Retrieval/QA needs to feel interactive — it never re-embeds the whole document, only the short user query, reusing everything ingestion already built.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Web framework | **FastAPI** + Uvicorn | Async-native, automatic OpenAPI docs, built-in Pydantic validation |
| Relational DB | **PostgreSQL 16** | Structured metadata + full-text search via `tsvector`, avoiding a separate search engine |
| ORM | **SQLAlchemy 2.0** (async) + Alembic | Type-safe async access; versioned schema migrations |
| Vector DB | **ChromaDB** | Purpose-built HNSW approximate-nearest-neighbor similarity search |
| Task queue | **Celery + Redis** | Runs slow PDF processing off the request path; Redis is the broker |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Small (384-dim), fast, CPU-friendly, free/local |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | More accurate final-stage relevance scoring |
| LLM | OpenAI `gpt-4o-mini` (swappable: Gemini / NVIDIA NIM / Groq) | Cheap, fast, reliable JSON-mode output; abstracted behind an interface |
| Auth | JWT (`python-jose`) + `bcrypt` | Stateless auth; industry-standard slow password hashing |
| Frontend | **React 18 + Vite** | Fast dev server, component model fits a multi-screen dashboard |
| Containerization | **Docker + docker-compose** | Reproducible multi-container setup (Postgres, Redis, Chroma, API, worker) |

---

## Project Structure

```
paperMind/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── api/v1/                    # Routers — HTTP layer only
│   │   ├── auth.py                 # register, login, /me
│   │   ├── papers.py               # upload, list, get, patch, delete, related
│   │   ├── search.py               # keyword/semantic/hybrid search
│   │   ├── qa.py                   # ask a grounded question
│   │   ├── analytics.py            # dashboard stats
│   │   └── users.py                # query history
│   ├── core/                      # Cross-cutting concerns
│   │   ├── config.py                # settings via Pydantic + .env
│   │   ├── security.py              # JWT + bcrypt helpers
│   │   └── logging.py
│   ├── db/
│   │   ├── session.py               # async SQLAlchemy engine/session
│   │   └── vector_store.py          # ChromaDB client wrapper
│   ├── models/models.py           # SQLAlchemy ORM table definitions
│   ├── schemas/schemas.py         # Pydantic request/response contracts
│   ├── providers/                 # Pluggable external integrations
│   │   ├── llm_provider.py          # OpenAI / Gemini / NVIDIA / Groq — one interface
│   │   └── storage_provider.py      # local filesystem save/load/delete
│   ├── services/                  # Business logic lives here
│   │   ├── ingestion_service.py     # orchestrates the upload pipeline
│   │   ├── chunker.py               # PDF text extraction + chunking
│   │   ├── metadata_extractor.py    # title/author/abstract/year/DOI extraction
│   │   ├── embedding_service.py     # text → vector
│   │   ├── retrieval_service.py     # keyword + semantic search + RRF fusion
│   │   ├── reranker_service.py      # cross-encoder reranking
│   │   ├── qa_service.py            # grounded-QA pipeline + citation rules
│   │   └── analytics_service.py     # dashboard aggregation, Redis-cached
│   └── workers/
│       ├── celery_app.py
│       └── tasks.py                 # process_paper task → ingestion_service
├── alembic/                       # Versioned DB migrations
├── docker/Dockerfile
├── docker-compose.yml
├── requirements.txt
└── frontend/                      # React application
```

Router files stay thin (HTTP concerns only); all real logic lives in `services/` — a clean separation of concerns that keeps retrieval/QA logic reusable outside the API layer.

---

## Database Schema

PostgreSQL, 5 tables (`app/models/models.py`, versioned by Alembic).

| Table | Purpose |
|---|---|
| **users** | One row per account. `bcrypt` password hash only, never plaintext. `role` is `user` or `admin`. |
| **papers** | One row per uploaded PDF — the central entity. Stores extracted bibliographic metadata, `file_hash` (unique, SHA-256), and `status` (`processing` → `ready`/`failed`). Indexed on `category` and `status`. |
| **chunks** | One row per text chunk. Its `id` is reused as the ChromaDB vector ID, linking the two databases. Includes an auto-populated `tsvector` column (`tsv`) via a Postgres trigger, backed by a GIN index for fast full-text search. |
| **search_history** | One row per search/QA request — powers History and Analytics. |
| **qa_citations** | One row per citation on a QA answer (many-to-one with `search_history`). Denormalizes `page_number`/`section_title` so citations stay stable even if the source chunk changes. |

```
users (1) —< papers (1) —< chunks
users (1) —< search_history (1) —< qa_citations >— papers/chunks
```

---

## Retrieval Strategy — Hybrid Search

Implemented in `retrieval_service.py` and `reranker_service.py`. A three-stage, multi-signal pipeline:

1. **Keyword search** — Postgres full-text search (`to_tsvector` / `plainto_tsquery` / `ts_rank_cd`), conceptually similar to BM25. Strong on exact terms, model names, acronyms; blind to paraphrasing.
2. **Semantic search** — Query embedded and compared via cosine similarity against ChromaDB's HNSW index. Strong on paraphrases and concepts; can under-weight rare, specific tokens.
3. **Reciprocal Rank Fusion (RRF)** — Since the two lists' scores live on incomparable scales, RRF fuses them by **rank position**: `score += 1 / (k + rank)` for each list a chunk appears in (`k = 60`). A chunk both methods agree on rises to the top.
4. **Cross-encoder reranking** (QA only) — `ms-marco-MiniLM-L-6-v2` scores the query and each of the top-20 RRF candidates *together* (not as two independent vectors), producing the final top 5 passages handed to the LLM. More accurate than the bi-encoder embedding step, but too slow to run over the whole corpus — hence "retrieve-then-rerank."

Plain search skips reranking to stay fast; QA uses it because answer quality depends heavily on exactly which 5 passages the LLM sees.

---

## Grounded QA & Citation Enforcement

Implemented in `qa_service.py::answer_question()` — retrieval + an LLM call + a validation layer that **never trusts the LLM's output blindly**.

**System prompt contract:**
1. Use ONLY the provided excerpts — no outside knowledge.
2. Every factual sentence ends with a `[n]` citation marker.
3. If the excerpts are insufficient, return the exact fallback: *"I could not find sufficient evidence in the uploaded papers."*
4. Never fabricate paper names, authors, numbers, or results.
5. Respond as strict JSON: `{answer, citations[], sufficient_evidence}`

The LLM call runs with `json_mode=True` and `temperature=0` for deterministic, parseable output.

**Server-side validation (`_validate_citations`):**
- **Sufficiency gate** — if `sufficient_evidence: false`, the model's text is discarded and replaced with the fixed fallback.
- **No hallucinated chunk IDs** — if any cited `chunk_id` isn't one of the 5 excerpts actually sent, the **entire answer is rejected**, not patched — a fabricated source undermines trust in the whole response.
- **No dangling `[n]` markers** — any marker in the prose without a matching citation entry is stripped from the text.
- **JSON parse retry** — one retry with an explicit "return only valid JSON" instruction; if that also fails, falls back gracefully instead of crashing.

This turns a probabilistic LLM call into a system with deterministic, auditable failure modes.

---

## Authentication & Security

- **Passwords**: hashed with `bcrypt` (slow + auto-salted) — never SHA-256, which is too fast and enables brute-forcing a leaked database.
- **JWT**: access token (15 min) + refresh token (7 days), signed with `HS256`. The user ID lives in the `sub` claim.
- **`get_current_user` dependency**: decodes/validates the JWT and loads the user before any route logic runs — rejects missing/expired/invalid tokens with `401` uniformly across the API.
- **Authorization**: `_check_owner()` enforces that only a paper's owner (or an `admin`) can edit/delete it.
- **Per-user data scoping**: every query — keyword search, semantic search, paper listing, analytics — is scoped by `user_id`, including inside the ChromaDB metadata filter itself, so cross-user data leakage is structurally impossible.
- **CORS**: currently `allow_origins=["*"]` for local dev — should be locked down before production.

---

## API Reference

| Method & Path | Purpose |
|---|---|
| `POST /auth/register` | Create an account (password ≥ 8 chars) |
| `POST /auth/login` | Exchange credentials for access + refresh tokens |
| `GET /auth/me` | Current user's profile |
| `POST /papers` | Upload a PDF (validated, deduped, `202 Accepted`, kicks off Celery) |
| `GET /papers` | List papers — filterable by category, year, status, title |
| `GET /papers/{id}` | Full paper detail |
| `GET /papers/{id}/status` | Lightweight polling endpoint |
| `PATCH /papers/{id}` | Edit metadata manually (owner/admin) |
| `DELETE /papers/{id}` | Delete paper + vectors + chunks (owner/admin) |
| `GET /papers/{id}/related` | Related papers (author overlap → category fallback) |
| `POST /search` | `{query, mode: keyword|semantic|hybrid, filters?, top_k}` — skips reranking |
| `POST /qa` | `{question, filters?}` → `{answer, citations, sufficient_evidence, search_history_id}` |
| `GET /analytics/overview` | Paper/chunk counts, categories, top authors, top queries (Redis-cached, 5 min) |
| `GET /users/me/history?limit=20` | Recent searches and questions |

Full interactive docs available at `/docs` (Swagger) and `/redoc` once running. Errors use a structured `{code, message}` body.

---

## Frontend

`frontend/src` — a React 18 + Vite single-page app. No Redux; plain `useState`/`useEffect` and one shared fetch wrapper (`utils/api.js`) that handles:

- Bearer token injection
- Correct `Content-Type` handling for JSON vs. file uploads (`FormData`)
- Global `401` → session-expired redirect (excluding `/auth/*` to avoid redirect loops on bad login)
- Unwrapping `{error: {code, message}}` into plain JS `Error`s

**Screens:** Library, Upload (drag-and-drop with live status polling), Search, Ask AI (renders `[1][2][3]` markers as clickable superscripts with a Sources panel), Analytics, History.

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- An LLM provider API key (OpenAI, Gemini, NVIDIA NIM, or Groq)

### Run with Docker Compose

```bash
git clone https://github.com/Aneelchoudhari/paperMind.git
cd paperMind
cp .env.example .env        # add your LLM_PROVIDER + API key, DB creds, secret_key
docker-compose up -d
```

This starts 5 services — `postgres`, `redis`, `chromadb`, `api`, `celery_worker` — using `depends_on` health checks so the API/worker wait until Postgres, Redis, and Chroma are actually ready (not just started). Database migrations (`alembic upgrade head`) run automatically on boot. ML models are pre-baked into the Docker image at build time (`HF_HUB_OFFLINE=1`), so containers start instantly with no runtime dependency on HuggingFace.

- API: `http://localhost:8000` (docs at `/docs`)
- Frontend: served separately from `frontend/` (`npm install && npm run dev`)

---

## Configuration

All settings are managed via `app/core/config.py` (`pydantic-settings`), reading from `.env` locally or real environment variables in Docker. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` | Celery broker / cache |
| `CHROMA_HOST` / `CHROMA_PORT` | Vector DB connection |
| `SECRET_KEY` | JWT signing secret — must be a secure value in production |
| `LLM_PROVIDER` | `openai` / `gemini` / `nvidia` / `groq` |
| `MAX_UPLOAD_SIZE_MB` | Default 50 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default 15 |
| `ANALYTICS_CACHE_TTL` | Default 5 min |

---

## Design Decisions & Trade-offs

- **Hybrid search over semantic-only**: embeddings can under-weight rare/exact tokens; keyword search is blind to paraphrasing. RRF combines both without hand-tuning a blended score.
- **Cross-encoder reranking only for QA**: too slow for the full corpus or for latency-sensitive plain search; worth it where citation precision matters most.
- **Postgres full-text search over Elasticsearch**: sufficient at this scale, and keeps keyword search in the same database as relational joins.
- **ChromaDB over `pgvector`**: two databases to keep in sync (mitigated by sharing UUIDs as primary keys) in exchange for a purpose-built HNSW implementation and richer vector-specific APIs. `pgvector` remains a valid alternative for less operational overhead.
- **Celery + Redis over `FastAPI.BackgroundTasks`**: ingestion is CPU-heavy; a real task queue allows independent worker scaling and built-in retries (`max_retries=3`).
- **Never trust LLM output as-is**: the single most important design philosophy — every LLM response is treated as an untrusted claim that must pass programmatic validation.
- **Pluggable LLM provider (Strategy pattern)**: `LLMProvider` abstract base class with 4 implementations; switching providers is a one-line `.env` change with zero code changes elsewhere.

---

## Known Limitations & Roadmap

- **No OCR support** — scanned image-only PDFs (no text layer) fail ingestion. *Planned: Tesseract fallback.*
- **Refresh token issued but never consumed** — no `/auth/refresh` endpoint yet exists; users are logged out after 15 minutes. *Planned: add the endpoint.*
- **QA rate limit configured but not enforced** — `qa_rate_limit_per_hour` exists in settings but isn't wired up. *Planned: Redis-backed sliding-window counter.*
- **CORS wide open** (`allow_origins=["*"]`) — fine for local dev, needs restricting before production.
- **Metadata heuristics can be fooled** by unconventional PDF layouts (e.g., a large subtitle vs. title); LLM fallback only triggers when title/authors are fully missing, not when a *wrong* value is confidently extracted.
- **No automated test suite currently present** — `pytest`/`pytest-asyncio` are listed as dependencies but no `tests/` directory exists yet.
- **Local filesystem storage** — won't survive multiple API replicas without a shared volume; an S3-compatible object store would be needed to scale horizontally.
- **Offset-based pagination** — fine at personal-library scale, could become slow on very large tables.

---

## Glossary

<details>
<summary>Click to expand full glossary of terms used in this project</summary>

- **RAG (Retrieval-Augmented Generation)** — Fetching relevant text from your own data before asking an LLM to answer, so the response is grounded in real, current, private information rather than pure memory.
- **Hallucination** — When an LLM generates confident but factually wrong or invented content.
- **Embedding** — A vector representing the meaning of text; similar meanings produce numerically close vectors.
- **Vector database** — A database specialized for storing embeddings and finding the closest ones to a query vector (ChromaDB here).
- **Cosine similarity** — Similarity between two vectors based on the angle between them.
- **HNSW** — The graph-based algorithm ChromaDB uses for fast approximate nearest-neighbor search.
- **BM25 / `ts_rank_cd`** — Classical keyword-ranking approaches that reward frequent-but-rare, distinctive query terms.
- **`tsvector` / `tsquery`** — Postgres's normalized text representations for full-text search.
- **GIN index** — A Postgres index type suited to full-text search and array containment.
- **Reciprocal Rank Fusion (RRF)** — Combines multiple ranked lists via `1/(k + rank)` scoring per list.
- **Bi-encoder** — Encodes query and passage independently, then compares vectors (fast, less precise).
- **Cross-encoder** — Encodes query and passage together, producing one relevance score (slower, more precise).
- **Chunking** — Splitting long documents into smaller retrievable pieces.
- **Token** — The unit an LLM processes; ~512 tokens ≈ 350–400 English words.
- **JWT** — A signed token representing an authenticated session without server-side storage.
- **bcrypt** — A deliberately slow, salted password-hashing algorithm.
- **ORM** — A library (SQLAlchemy) mapping Python classes to SQL tables.
- **Alembic** — Version-controlled database schema migrations.
- **Celery** — A distributed task queue for background jobs.
- **Redis** — An in-memory store used as Celery's broker and for caching.
- **Dependency injection (FastAPI `Depends`)** — Framework-supplied parameters (e.g., DB session, current user) before a route runs.
- **CORS** — Browser mechanism restricting which origins can call your API.
- **SHA-256** — A one-way hash used here purely for exact-duplicate file detection.

</details>

---

## License

No license file is currently included in this repository, which means all rights are reserved by default — others can view the code but have no legal right to reuse, modify, or distribute it. If you'd like to allow reuse, consider adding an [MIT](https://choosealicense.com/licenses/mit/) or [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/) `LICENSE` file.

## Repository

[github.com/Aneelchoudhari/paperMind](https://github.com/Aneelchoudhari/paperMind)

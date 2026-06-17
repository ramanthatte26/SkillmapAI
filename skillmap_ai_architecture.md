# SkillMap AI — MVP Architecture Blueprint

> **Goal**: Convert YouTube playlists into structured learning roadmaps with progress tracking and AI-generated notes.
> **Stack**: Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui | FastAPI · SQLAlchemy · PostgreSQL · JWT Auth

---

## Table of Contents
1. [Folder Structure](#1-folder-structure)
2. [Database Schema](#2-database-schema)
3. [SQLAlchemy Models](#3-sqlalchemy-models)
4. [Pydantic Schemas](#4-pydantic-schemas)
5. [API Route Design](#5-api-route-design)
6. [Authentication Architecture](#6-authentication-architecture)
7. [Environment Variables](#7-environment-variables)
8. [requirements.txt](#8-requirementstxt)
9. [Setup Instructions](#9-setup-instructions)
10. [Git Commands](#10-git-commands)

---

## 1. Folder Structure

```
skillmap-ai/
│
├── README.md
├── .gitignore
│
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app factory + CORS
│   │   ├── config.py                 # Pydantic Settings (env vars)
│   │   ├── database.py               # SQLAlchemy engine + session
│   │   │
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # DeclarativeBase + shared mixins
│   │   │   ├── user.py
│   │   │   ├── roadmap.py
│   │   │   ├── video.py
│   │   │   └── progress.py
│   │   │
│   │   ├── schemas/                  # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── roadmap.py
│   │   │   ├── video.py
│   │   │   └── progress.py
│   │   │
│   │   ├── routers/                  # FastAPI APIRouter modules
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── roadmaps.py
│   │   │   ├── videos.py
│   │   │   └── progress.py
│   │   │
│   │   ├── services/                 # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py       # JWT creation, validation, hashing
│   │   │   ├── youtube_service.py    # YouTube Data API v3 calls
│   │   │   ├── ai_service.py         # Google Gemini / OpenAI calls
│   │   │   └── roadmap_service.py    # Roadmap generation orchestration
│   │   │
│   │   ├── dependencies/             # FastAPI Depends() callables
│   │   │   ├── __init__.py
│   │   │   ├── db.py                 # get_db() session generator
│   │   │   └── auth.py               # get_current_user()
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── exceptions.py         # Custom HTTP exceptions
│   │
│   ├── alembic/                      # Database migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_roadmaps.py
│   │   └── test_videos.py
│   │
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env                          # NOT committed to git
│
└── frontend/                         # Next.js 15 application
    ├── app/                          # App Router
    │   ├── layout.tsx
    │   ├── page.tsx                  # Landing page
    │   ├── (auth)/
    │   │   ├── login/page.tsx
    │   │   └── register/page.tsx
    │   ├── (dashboard)/
    │   │   ├── layout.tsx            # Protected layout
    │   │   ├── dashboard/page.tsx
    │   │   ├── roadmaps/
    │   │   │   ├── page.tsx          # List all roadmaps
    │   │   │   ├── new/page.tsx      # Create from playlist URL
    │   │   │   └── [id]/
    │   │   │       ├── page.tsx      # Roadmap detail + progress
    │   │   │       └── notes/page.tsx
    │   │   └── profile/page.tsx
    │   └── api/                      # Next.js Route Handlers (proxy layer)
    │       └── auth/[...nextauth]/route.ts
    │
    ├── components/
    │   ├── ui/                       # shadcn/ui auto-generated
    │   ├── layout/
    │   │   ├── Navbar.tsx
    │   │   └── Sidebar.tsx
    │   ├── roadmap/
    │   │   ├── RoadmapCard.tsx
    │   │   ├── RoadmapTimeline.tsx
    │   │   └── VideoItem.tsx
    │   └── auth/
    │       ├── LoginForm.tsx
    │       └── RegisterForm.tsx
    │
    ├── lib/
    │   ├── api.ts                    # Axios/fetch wrapper with base URL
    │   ├── auth.ts                   # Token storage helpers
    │   └── utils.ts                  # shadcn cn() util
    │
    ├── hooks/
    │   ├── useAuth.ts
    │   └── useRoadmap.ts
    │
    ├── types/
    │   └── index.ts                  # Shared TypeScript interfaces
    │
    ├── middleware.ts                  # Next.js route protection
    ├── tailwind.config.ts
    ├── next.config.ts
    ├── tsconfig.json
    ├── package.json
    └── .env.local                    # NOT committed to git
```

> **Why this structure?**
> - **Feature-adjacent** grouping inside `app/` (auth, dashboard) mirrors Next.js App Router conventions and avoids a flat component soup.
> - **Service layer** in FastAPI cleanly separates business logic from HTTP concerns — routers only validate input and delegate; services do the work. This is the **Dependency Inversion Principle** and makes unit testing trivial.
> - **`dependencies/`** folder isolates all `Depends()` callables — your auth guard (`get_current_user`) lives in one place and is imported everywhere, not re-defined per router.

---

## 2. Database Schema

### Entity Relationship (Conceptual)

```
users ──< roadmaps ──< videos ──< video_progress
                 │                    │
                 └────────────────────┘
                   (roadmap_id links both)
```

### Tables

```sql
-- ─────────────────────────────────────────
-- users
-- ─────────────────────────────────────────
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    username    VARCHAR(100) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- roadmaps  (one playlist → one roadmap)
-- ─────────────────────────────────────────
CREATE TABLE roadmaps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    playlist_url    TEXT NOT NULL,
    playlist_id     VARCHAR(100) NOT NULL,   -- YouTube playlist ID (e.g. PLxxxx)
    thumbnail_url   TEXT,
    total_videos    INT DEFAULT 0,
    completed_videos INT DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'processing'
                    CHECK (status IN ('processing','active','archived')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- videos  (one roadmap → many videos)
-- ─────────────────────────────────────────
CREATE TABLE videos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    roadmap_id      UUID NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    youtube_id      VARCHAR(20) NOT NULL,    -- YouTube video ID (11 chars)
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    thumbnail_url   TEXT,
    duration_seconds INT,
    position        INT NOT NULL,            -- order within roadmap
    ai_notes        TEXT,                    -- AI-generated summary
    ai_notes_status VARCHAR(20) DEFAULT 'pending'
                    CHECK (ai_notes_status IN ('pending','generating','done','failed')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────
-- video_progress  (tracks per-user per-video state)
-- ─────────────────────────────────────────
CREATE TABLE video_progress (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id        UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    roadmap_id      UUID NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    is_completed    BOOLEAN DEFAULT FALSE,
    watch_time_seconds INT DEFAULT 0,
    user_notes      TEXT,                    -- User's own notes
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, video_id)               -- one progress row per user-video pair
);

-- ─────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────
CREATE INDEX idx_roadmaps_user_id       ON roadmaps(user_id);
CREATE INDEX idx_videos_roadmap_id      ON videos(roadmap_id);
CREATE INDEX idx_videos_position        ON videos(roadmap_id, position);
CREATE INDEX idx_progress_user_roadmap  ON video_progress(user_id, roadmap_id);
CREATE INDEX idx_progress_user_video    ON video_progress(user_id, video_id);
```

> **Why UUIDs over serial integers?**
> UUIDs are non-sequential and safe to expose in URLs — no enumeration attacks. PostgreSQL's `gen_random_uuid()` (v4) is built-in from PG 13+.
>
> **Why `ON DELETE CASCADE`?**
> Deleting a user removes all their roadmaps/progress atomically at the DB level — no orphan rows and no application-level cleanup needed.
>
> **Why `UNIQUE (user_id, video_id)` on progress?**
> Enforces one progress record per (user, video) pair at the database level — not just in application code. Eliminates duplicate-insert bugs under concurrent requests.

---

## 3. SQLAlchemy Models

> **Architecture Decision**: All models inherit from a shared `Base` class and a `TimestampMixin`. This keeps timestamp columns DRY and ensures consistent auditing across all tables.

### `app/models/base.py`
```python
# Architectural sketch — not implementation code
# DeclarativeBase from SQLAlchemy 2.0 (mapped_column, Mapped[] type hints)
# TimestampMixin: created_at, updated_at with server_default=func.now()
# All PKs: Mapped[uuid.UUID] with default_factory=uuid4
```

### `app/models/user.py`
```python
# Table: users
# Columns:
#   id: UUID PK
#   email: str (unique, indexed)
#   username: str (unique, indexed)
#   hashed_password: str
#   is_active: bool (default True)
#   is_verified: bool (default False)
# Relationships:
#   roadmaps → List["Roadmap"] (back_populates="user", cascade="all, delete-orphan")
#   progress → List["VideoProgress"] (back_populates="user")
```

### `app/models/roadmap.py`
```python
# Table: roadmaps
# Columns:
#   id: UUID PK
#   user_id: UUID FK → users.id
#   title, description, playlist_url, playlist_id
#   thumbnail_url, total_videos, completed_videos
#   status: Enum("processing", "active", "archived")
# Relationships:
#   user → "User" (back_populates="roadmaps")
#   videos → List["Video"] (back_populates="roadmap", order_by=Video.position, cascade="all, delete-orphan")
```

### `app/models/video.py`
```python
# Table: videos
# Columns:
#   id: UUID PK
#   roadmap_id: UUID FK → roadmaps.id
#   youtube_id, title, description, thumbnail_url
#   duration_seconds: int
#   position: int (ordering)
#   ai_notes: str | None
#   ai_notes_status: Enum("pending","generating","done","failed")
# Relationships:
#   roadmap → "Roadmap" (back_populates="videos")
#   progress → List["VideoProgress"] (back_populates="video")
```

### `app/models/progress.py`
```python
# Table: video_progress
# Columns:
#   id: UUID PK
#   user_id: UUID FK → users.id
#   video_id: UUID FK → videos.id
#   roadmap_id: UUID FK → roadmaps.id (denormalized for fast roadmap-level queries)
#   is_completed: bool
#   watch_time_seconds: int
#   user_notes: str | None
#   completed_at: datetime | None
# UniqueConstraint: (user_id, video_id)
# Relationships:
#   user → "User", video → "Video", roadmap → "Roadmap"
```

> **Why SQLAlchemy 2.0 `Mapped[]` style?**
> It provides full type-safety — `mypy` and your IDE can infer column types without stubs. The old `Column()` style loses type info at the class level.
>
> **Why denormalize `roadmap_id` on `video_progress`?**
> Fetching all progress for a roadmap dashboard page would otherwise require a JOIN through `videos` → `video_progress`. Storing `roadmap_id` directly makes that a single-table index scan.

---

## 4. Pydantic Schemas

> **Architecture Decision**: Use separate **Request** and **Response** schemas. Never use ORM models as API responses directly — this leaks internal fields (`hashed_password`) and tightly couples DB schema to API contract.

### `app/schemas/auth.py`
```python
# RegisterRequest:   email, username, password (min 8 chars, validated)
# LoginRequest:      email, password
# TokenResponse:     access_token: str, token_type: str = "bearer"
# TokenPayload:      sub: str (user_id), exp: datetime
```

### `app/schemas/user.py`
```python
# UserCreate:        email, username, password
# UserResponse:      id, email, username, is_active, created_at
#                    (NO hashed_password — ever)
# UserUpdate:        username?, email? (all optional fields)
```

### `app/schemas/roadmap.py`
```python
# RoadmapCreate:     playlist_url (validated as YouTube URL)
# RoadmapResponse:   id, title, description, playlist_url,
#                    thumbnail_url, total_videos, completed_videos,
#                    status, created_at, videos: List[VideoResponse]
# RoadmapSummary:    id, title, thumbnail_url, status,
#                    total_videos, completed_videos
#                    (used in list endpoints — no nested videos)
```

### `app/schemas/video.py`
```python
# VideoResponse:     id, youtube_id, title, thumbnail_url,
#                    duration_seconds, position, ai_notes_status
# VideoDetailResponse: VideoResponse + ai_notes (only fetched on detail view)
```

### `app/schemas/progress.py`
```python
# ProgressUpdate:    is_completed: bool, watch_time_seconds?: int, user_notes?: str
# ProgressResponse:  id, video_id, roadmap_id, is_completed,
#                    watch_time_seconds, user_notes, completed_at
```

> **Why `RoadmapSummary` vs `RoadmapResponse`?**
> The list endpoint (`GET /roadmaps`) returns many roadmaps — serializing all nested videos would be an **N+1 query disaster**. `RoadmapSummary` avoids loading video collections entirely. The detail endpoint (`GET /roadmaps/{id}`) can afford the full graph with `selectinload`.

---

## 5. API Route Design

### Base URL: `/api/v1`

> **Architecture Decision**: Version the API from day one (`/v1`). When breaking changes are needed, `/v2` can coexist without client disruption.

---

#### 🔐 Auth — `/api/v1/auth`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | ❌ | Create user account |
| `POST` | `/auth/login` | ❌ | Login, returns JWT |
| `POST` | `/auth/refresh` | ✅ | Refresh access token |
| `POST` | `/auth/logout` | ✅ | Invalidate refresh token |

---

#### 👤 Users — `/api/v1/users`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/users/me` | ✅ | Get current user profile |
| `PATCH` | `/users/me` | ✅ | Update profile |
| `DELETE` | `/users/me` | ✅ | Delete account (cascade) |

---

#### 🗺️ Roadmaps — `/api/v1/roadmaps`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/roadmaps` | ✅ | List user's roadmaps (paginated) |
| `POST` | `/roadmaps` | ✅ | Create roadmap from playlist URL |
| `GET` | `/roadmaps/{id}` | ✅ | Get roadmap + videos |
| `PATCH` | `/roadmaps/{id}` | ✅ | Update title / archive |
| `DELETE` | `/roadmaps/{id}` | ✅ | Delete roadmap |

---

#### 🎬 Videos — `/api/v1/roadmaps/{roadmap_id}/videos`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/roadmaps/{roadmap_id}/videos` | ✅ | List all videos in roadmap |
| `GET` | `/roadmaps/{roadmap_id}/videos/{id}` | ✅ | Video detail + AI notes |
| `POST` | `/roadmaps/{roadmap_id}/videos/{id}/generate-notes` | ✅ | Trigger AI note generation |

---

#### 📊 Progress — `/api/v1/progress`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/progress/roadmap/{roadmap_id}` | ✅ | All progress for a roadmap |
| `PUT` | `/progress/video/{video_id}` | ✅ | Upsert video progress |
| `GET` | `/progress/stats` | ✅ | Aggregated learning stats |

---

> **Why nested videos under roadmaps?**
> `/roadmaps/{id}/videos` makes the relationship self-documenting in the URL. A video without a roadmap context doesn't make sense to the consumer.
>
> **Why `PUT` for progress upsert?**
> Progress is idempotent — calling it twice with the same data has the same result. `PUT` is semantically correct here. Under the hood this maps to `INSERT ... ON CONFLICT DO UPDATE`.
>
> **Why paginate `/roadmaps`?**
> A user could accumulate dozens of roadmaps. Returning all at once is an unbounded query. Default: `?page=1&limit=12`.

---

## 6. Authentication Architecture

### Flow Diagram (Textual)
```
Client                        FastAPI Backend              PostgreSQL
  │                                │                           │
  │── POST /auth/register ────────>│                           │
  │                                │── INSERT user ───────────>│
  │<── 201 UserResponse ───────────│                           │
  │                                │                           │
  │── POST /auth/login ───────────>│                           │
  │                                │── SELECT user by email ──>│
  │                                │   bcrypt.verify(pw)       │
  │<── 200 {access_token,          │                           │
  │         refresh_token} ────────│                           │
  │                                │                           │
  │── GET /roadmaps ───────────────│                           │
  │   Authorization: Bearer <JWT>  │                           │
  │                                │── decode JWT              │
  │                                │── SELECT user by id ─────>│
  │<── 200 RoadmapList ────────────│                           │
```

### JWT Strategy

| Token | Lifetime | Storage (client) | Purpose |
|-------|----------|-----------------|---------|
| **Access Token** | 15 minutes | Memory / JS variable | Authorizes API calls |
| **Refresh Token** | 7 days | `httpOnly` cookie | Obtains new access tokens |

```
JWT Payload (access token):
{
  "sub": "<user_uuid>",
  "email": "user@example.com",
  "exp": <unix_timestamp>,
  "iat": <unix_timestamp>,
  "type": "access"
}
```

### Security Decisions

1. **`python-jose` + `passlib[bcrypt]`** — industry standard; bcrypt work factor default 12.
2. **Access token in memory** (not localStorage) — immune to XSS token theft.
3. **Refresh token in `httpOnly` cookie** — immune to JS-based theft; CSRF-protected via `SameSite=Lax`.
4. **`get_current_user` dependency** — every protected route declares `user: User = Depends(get_current_user)`. FastAPI handles 401 automatically if the dependency raises `HTTPException`.
5. **No token blacklist (MVP)** — for MVP, short-lived access tokens + refresh rotation is sufficient. A Redis-based blacklist can be added post-MVP for `logout` hardening.

### Password Hashing
```
bcrypt cost factor: 12  (≈ 250ms on modern hardware — brute-force resistant)
Library: passlib[bcrypt]
Never log, store, or transmit plaintext passwords
```

---

## 7. Environment Variables

### Backend — `backend/.env`

```ini
# ─── Application ───────────────────────────────
APP_NAME=SkillMap AI
APP_ENV=development                   # development | staging | production
DEBUG=True
SECRET_KEY=your-super-secret-key-min-32-chars   # openssl rand -hex 32

# ─── Database ──────────────────────────────────
DATABASE_URL=postgresql+psycopg2://skillmap_user:password@localhost:5432/skillmap_db
# Async alternative (if using asyncpg):
# DATABASE_URL=postgresql+asyncpg://...

# ─── JWT ───────────────────────────────────────
JWT_SECRET_KEY=your-jwt-secret-key-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── YouTube Data API v3 ───────────────────────
YOUTUBE_API_KEY=your-youtube-data-api-v3-key

# ─── AI (choose one) ───────────────────────────
GOOGLE_API_KEY=your-gemini-api-key
# OPENAI_API_KEY=your-openai-api-key            # alternative

# ─── CORS ──────────────────────────────────────
FRONTEND_URL=http://localhost:3000

# ─── Email (optional for verification) ────────
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=
# SMTP_PASSWORD=
```

### Frontend — `frontend/.env.local`

```ini
# ─── Backend API ───────────────────────────────
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

# ─── App ───────────────────────────────────────
NEXT_PUBLIC_APP_NAME=SkillMap AI
```

> **Why `NEXT_PUBLIC_` prefix?**
> Next.js only exposes env vars to the browser bundle if they're prefixed with `NEXT_PUBLIC_`. Server-only secrets (API keys) must NOT have this prefix.
>
> **Why split `SECRET_KEY` and `JWT_SECRET_KEY`?**
> They serve different purposes. `SECRET_KEY` is the FastAPI app secret (used for session/cookie signing), while `JWT_SECRET_KEY` is the HMAC key for JWT signing. Keeping them separate allows rotation independently.

### `app/config.py` (Pydantic Settings sketch)
```python
# class Settings(BaseSettings):
#     app_name: str
#     debug: bool = False
#     database_url: str
#     jwt_secret_key: str
#     jwt_algorithm: str = "HS256"
#     access_token_expire_minutes: int = 15
#     refresh_token_expire_days: int = 7
#     youtube_api_key: str
#     google_api_key: str
#     frontend_url: str
#
#     model_config = SettingsConfigDict(env_file=".env")
#
# @lru_cache
# def get_settings() -> Settings: ...
```

> **Why `@lru_cache` on `get_settings()`?**
> `.env` is read from disk once and cached for the process lifetime — no repeated I/O on every request.

---

## 8. requirements.txt

```
# ─── Web Framework ─────────────────────────────
fastapi==0.115.5
uvicorn[standard]==0.32.1

# ─── Database ──────────────────────────────────
sqlalchemy==2.0.36
psycopg2-binary==2.9.10       # sync PostgreSQL driver
alembic==1.14.0               # schema migrations

# ─── Validation & Settings ─────────────────────
pydantic==2.10.3
pydantic-settings==2.6.1

# ─── Authentication ────────────────────────────
python-jose[cryptography]==3.3.0   # JWT encode/decode
passlib[bcrypt]==1.7.4             # password hashing

# ─── HTTP Client (for YouTube API calls) ───────
httpx==0.28.1

# ─── AI Integrations ───────────────────────────
google-generativeai==0.8.3    # Gemini
# openai==1.57.0              # alternative

# ─── Utilities ─────────────────────────────────
python-multipart==0.0.18      # form data / file uploads
python-dotenv==1.0.1

# ─── Development / Testing ─────────────────────
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.28.1                 # async test client for FastAPI
```

> **Why `psycopg2-binary` for MVP?**
> The binary distribution bundles C extensions — no system `libpq` install required. For production, compile from source (`psycopg2` without `-binary`) to avoid dependency on the pre-built binary.
>
> **Why `httpx` and not `requests`?**
> FastAPI's `TestClient` is built on `httpx`. Using `httpx` everywhere (tests + YouTube API calls) keeps the dependency count minimal.
>
> **Why `alembic` from day one?**
> Running raw `CREATE TABLE` SQL in dev and then using Alembic in production creates drift. Start with Alembic immediately — every schema change is a versioned migration file committed to Git.

---

## 9. Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 20+ and npm
- PostgreSQL 15+
- Git

---

### Step 1 — Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/skillmap-ai.git
cd skillmap-ai
```

### Step 2 — PostgreSQL Database Setup
```bash
# Log into PostgreSQL
psql -U postgres

# Inside psql shell:
CREATE USER skillmap_user WITH PASSWORD 'your_password';
CREATE DATABASE skillmap_db OWNER skillmap_user;
GRANT ALL PRIVILEGES ON DATABASE skillmap_db TO skillmap_user;
\q
```

### Step 3 — Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, API keys, secrets

# Initialize Alembic (first time only)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "initial schema"

# Apply migrations to database
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --port 8000
```

> API docs available at: `http://localhost:8000/docs` (Swagger UI)

### Step 4 — Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local with your NEXT_PUBLIC_API_BASE_URL

# Run development server
npm run dev
```

> App available at: `http://localhost:3000`

### Step 5 — Verify the Stack
```bash
# Test backend health (in a new terminal)
curl http://localhost:8000/health

# Expected response:
# {"status": "ok", "version": "1.0.0"}
```

---

## 10. Git Commands

### Initialize and Configure (already done if cloned)
```bash
# If starting fresh (not cloned):
git init
git branch -M main

# Configure identity (if not globally set)
git config user.name "Your Name"
git config user.email "your@email.com"
```

### Create `.gitignore`
```bash
# Create root .gitignore:
cat > .gitignore << 'EOF'
# Python
backend/venv/
backend/__pycache__/
backend/**/__pycache__/
backend/**/*.pyc
backend/.env
backend/*.egg-info/

# Alembic
backend/alembic/versions/__pycache__/

# Node
frontend/node_modules/
frontend/.next/
frontend/.env.local
frontend/out/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
EOF
```

### Initial Commit
```bash
git add .
git commit -m "chore: initial project scaffold

- Add backend FastAPI folder structure
- Add frontend Next.js 15 folder structure
- Add database schema design
- Add SQLAlchemy models (skeleton)
- Add Pydantic schemas (skeleton)
- Add requirements.txt
- Add environment variable templates
- Add Alembic migration setup
- Add README with setup instructions"
```

### Create Remote and Push
```bash
# On GitHub: create new repo named 'skillmap-ai' (do NOT initialize with README)

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/skillmap-ai.git

# Push
git push -u origin main
```

### Branch Strategy (Recommended for Portfolio)
```bash
# Feature branches — shows professional Git workflow to interviewers
git checkout -b feat/auth-jwt
git checkout -b feat/youtube-integration
git checkout -b feat/roadmap-generation
git checkout -b feat/ai-notes
git checkout -b feat/progress-tracking

# Merge via PR on GitHub (demonstrates code review workflow)
```

### Useful Git Aliases for Development
```bash
git config alias.lg "log --oneline --graph --decorate"
git config alias.st "status -sb"
git config alias.cm "commit -m"
```

---

## Architectural Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| DB primary keys | UUID v4 | Security (no enumeration), distributed-safe |
| ORM style | SQLAlchemy 2.0 `Mapped[]` | Full type safety, IDE support |
| Migration tool | Alembic | Industry standard, auto-generates diffs |
| Auth tokens | JWT (access + refresh) | Stateless, scalable, no session store needed |
| Access token storage | JS memory | XSS-safe; not localStorage |
| Refresh token storage | `httpOnly` cookie | XSS-safe, CSRF mitigated via SameSite=Lax |
| Password hashing | bcrypt (cost=12) | OWASP recommended, time-hardened |
| API versioning | `/api/v1` prefix | Non-breaking evolution path |
| Schema separation | Request ≠ Response | Prevents internal field leakage |
| Settings management | Pydantic Settings + `@lru_cache` | Type-safe, DRY, fast |
| Frontend routing | Next.js App Router (route groups) | Clean auth/dashboard separation |
| State management | TBD (React Context or Zustand) | Context for auth; Zustand if state grows |

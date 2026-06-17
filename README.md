# SkillMap AI

A web application that converts YouTube playlists into structured learning roadmaps with progress tracking and AI-generated notes.

## Tech Stack

**Backend:** FastAPI · SQLAlchemy 2.0 · PostgreSQL · JWT Authentication  
**Frontend:** Next.js 15 · TypeScript · Tailwind CSS · shadcn/ui *(coming soon)*

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # Fill in your values
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Project Structure

```
skillmap-ai/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── dependencies/
│   │   └── utils/
│   └── alembic/      # Database migrations
└── frontend/         # Next.js 15 (coming soon)
```

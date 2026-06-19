"""
SkillMap AI — Video Notes Integration Test
Tests the new POST/GET /videos/{id}/notes endpoints end-to-end.
Run from backend/ directory: venv\Scripts\python test_notes_e2e.py
"""
import json
import os
import uuid
import logging

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.base import Base
from app.models.user import User
from app.models.roadmap import Roadmap, RoadmapStatus
from app.models.video import Video, AINotesStatus
from app.models.module import Module, ModuleVideo
from app.dependencies.db import get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("test_notes_e2e")

# ── PostgreSQL Database (default settings) ─────────────────────────
client = TestClient(app)



def create_user_and_token():
    suffix = uuid.uuid4().hex[:8]
    resp = client.post("/api/v1/auth/register", json={
        "email": f"notes_{suffix}@example.com",
        "username": f"notesuser{suffix}",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    data = resp.json()
    return data["user"]["id"], data["access_token"]


def seed_roadmap_and_video(user_id: str) -> tuple[str, str]:
    """Insert roadmap + video directly and return their IDs."""
    db = next(get_db())
    try:
        roadmap = Roadmap(
            user_id=uuid.UUID(user_id),
            title="Python Full Course",
            description="Learn Python from scratch.",
            playlist_url="https://www.youtube.com/playlist?list=PL_fake",
            playlist_id="PL_fake",
            total_videos=1,
            completed_videos=0,
            status=RoadmapStatus.ACTIVE,
        )
        db.add(roadmap)
        db.flush()

        video = Video(
            roadmap_id=roadmap.id,
            youtube_id="dQw4w9WgXcQ",
            title="Python Variables and Data Types",
            description="Learn about variables, data types, int, float, str, bool.",
            duration_seconds=600,
            position=1,
            ai_notes=None,
            ai_notes_status=AINotesStatus.PENDING,
        )
        db.add(video)
        db.commit()
        return str(roadmap.id), str(video.id)
    finally:
        db.close()



def run():
    print("\n" + "=" * 60)
    print("  VIDEO NOTES E2E TESTS")
    print("=" * 60)

    # Setup
    user_id, token = create_user_and_token()
    headers = {"Authorization": f"Bearer {token}"}
    roadmap_id, video_id = seed_roadmap_and_video(user_id)
    print(f"  Seeded: user={user_id[:8]}... roadmap={roadmap_id[:8]}... video={video_id[:8]}...")

    # ── Test 1: GET notes before generation → 404 ─────────────────
    resp = client.get(f"/api/v1/videos/{video_id}/notes", headers=headers)
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
    print("  GET /notes (before generate)        -> 404 OK")

    # ── Test 2: POST generate-notes ───────────────────────────────
    print("  POST /generate-notes (calling OpenRouter - ~10s) ...")
    resp = client.post(f"/api/v1/videos/{video_id}/generate-notes", headers=headers)
    assert resp.status_code == 200, f"generate-notes failed {resp.status_code}: {resp.text}"
    notes = resp.json()
    print("  POST /generate-notes                -> 200 OK")
    print(f"\n  Notes payload:")
    print(f"    status           : {notes['ai_notes_status']}")
    print(f"    summary          : {notes['summary'][:90]}...")
    print(f"    key_concepts     : {notes['key_concepts']}")
    print(f"    important_terms  : {notes['important_terms']}")
    print(f"    interview_qs     : {notes['interview_questions']}")

    # ── Test 3: Validate shape ────────────────────────────────────
    assert notes["ai_notes_status"] == "done", f"Expected 'done', got {notes['ai_notes_status']}"
    assert isinstance(notes["summary"], str) and notes["summary"], "summary must be non-empty str"
    assert isinstance(notes["key_concepts"], list) and notes["key_concepts"], "key_concepts must be non-empty"
    assert isinstance(notes["important_terms"], list) and notes["important_terms"], "important_terms must be non-empty"
    assert isinstance(notes["interview_questions"], list) and notes["interview_questions"], "interview_questions must be non-empty"
    print("\n  Schema validation                   -> OK")

    # ── Test 4: GET notes after generation → 200 (cached) ─────────
    resp = client.get(f"/api/v1/videos/{video_id}/notes", headers=headers)
    assert resp.status_code == 200, f"GET notes failed {resp.status_code}: {resp.text}"
    cached = resp.json()
    assert cached["summary"] == notes["summary"], "Cached notes mismatch"
    print("  GET /notes (after generate)         -> 200 with cached data OK")

    # ── Test 5: GET roadmap detail includes ai_notes ──────────────
    resp = client.get(f"/api/v1/roadmaps/{roadmap_id}", headers=headers)
    assert resp.status_code == 200, f"GET roadmap failed: {resp.status_code}"
    detail = resp.json()
    video_data = next((v for v in detail["videos"] if v["id"] == video_id), None)
    assert video_data is not None, "Video not found in roadmap detail"
    assert video_data["ai_notes_status"] == "done", f"Expected 'done', got {video_data['ai_notes_status']}"
    assert video_data["ai_notes"] is not None, "ai_notes should not be null after generation"
    parsed = json.loads(video_data["ai_notes"])
    assert "summary" in parsed, "ai_notes JSON must contain 'summary'"
    print("  GET /roadmaps/{id} includes ai_notes -> OK")

    # ── Test 6: Ownership security ────────────────────────────────
    _, other_token = create_user_and_token()
    resp = client.post(
        f"/api/v1/videos/{video_id}/generate-notes",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    print("  Other user POST /generate-notes     -> 403 OK")

    resp = client.get(
        f"/api/v1/videos/{video_id}/notes",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    print("  Other user GET /notes               -> 403 OK")

    print("\n" + "=" * 60)
    print("  ALL NOTES TESTS PASSED!")
    print("=" * 60 + "\n")



if __name__ == "__main__":
    run()


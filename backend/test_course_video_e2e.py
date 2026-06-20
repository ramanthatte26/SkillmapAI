"""
SkillMap AI — Single Course Video Import Integration Test
Tests the full pipeline from POST /api/v1/course-video/import to curriculum segmentation,
database mapping, AI notes generation, vector search indexing, and deep-link verification.
Run from backend/ directory: venv\\Scripts\\python test_course_video_e2e.py
"""

import json
import os
import uuid
import logging
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.roadmap import Roadmap, RoadmapStatus
from app.models.video import Video, AINotesStatus
from app.models.module import Module, ModuleVideo
from app.dependencies.db import get_db
from app.services.search_service import SearchService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("test_course_video_e2e")

client = TestClient(app)

def create_user_and_token(suffix: str) -> tuple[str, str]:
    resp = client.post("/api/v1/auth/register", json={
        "email": f"course_{suffix}@example.com",
        "username": f"courseuser{suffix}",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    data = resp.json()
    return data["user"]["id"], data["access_token"]

# Mock data
MOCK_METADATA = {
    "youtube_id": "rfscVS0vtbw",
    "title": "Full Python Course for Beginners",
    "description": "Learn python programming step by step.",
    "thumbnail_url": "https://img.youtube.com/vi/rfscVS0vtbw/maxresdefault.jpg",
    "duration_seconds": 1800, # 30 minutes
}

MOCK_TRANSCRIPT = [
    {"text": "welcome to python course, today we talk about syntax and variables", "start": 0.0, "duration": 10.0},
    {"text": "syntax is indent based. let's write code", "start": 30.0, "duration": 15.0},
    {"text": "next we discuss loops and if statements", "start": 600.0, "duration": 20.0},
    {"text": "for loops iterate over sequences. while loops continue until condition is false", "start": 620.0, "duration": 25.0},
    {"text": "finally we discuss classes and object oriented programming", "start": 1200.0, "duration": 30.0},
    {"text": "classes define blueprints for objects. we instantiate objects using them", "start": 1230.0, "duration": 15.0},
]

MOCK_CURRICULUM = [
    {
        "name": "Python Syntax and Variables",
        "description": "Learn the basic indentation syntax and variable declarations in Python.",
        "start_timestamp_seconds": 0
    },
    {
        "name": "Control Flow and Loops",
        "description": "Learn about if-else conditionals and for/while loop iteration.",
        "start_timestamp_seconds": 600
    },
    {
        "name": "Object-Oriented Programming in Python",
        "description": "Master classes, attributes, methods, and instantiation.",
        "start_timestamp_seconds": 1200
    }
]

def mock_generate_video_notes(video_title: str, roadmap_title: str, module_name: str, video_description: str):
    return {
        "summary": f"This segment covers {video_title} which is part of {module_name}.",
        "key_concepts": [video_title, "Programming", "Python"],
        "important_terms": ["Reference", "Syntax", "Logic"],
        "interview_questions": [f"Explain the main ideas in {video_title}."]
    }

# ── Monkeypatching class methods ───────────────────────────────────────────
from youtube_transcript_api import YouTubeTranscriptApi, FetchedTranscriptSnippet
def mock_fetch(self, video_id, languages=None, preserve_formatting=False):
    return [
        FetchedTranscriptSnippet(text=t["text"], start=t["start"], duration=t["duration"])
        for t in MOCK_TRANSCRIPT
    ]
YouTubeTranscriptApi.fetch = mock_fetch

from app.services.youtube_service import YouTubeService
YouTubeService.fetch_video_metadata = lambda self, video_id: MOCK_METADATA

from app.services.ai_service import AIService
AIService.extract_course_curriculum = lambda self, roadmap_title, timestamped_transcript, total_duration_seconds: ("This Python course covers basic python concepts.", MOCK_CURRICULUM)
AIService.generate_video_notes = lambda self, video_title, roadmap_title, module_name=None, video_description=None, transcript_text=None: mock_generate_video_notes(video_title, roadmap_title, module_name or "", video_description or "")


def run_tests():
    print("\n" + "=" * 60)
    print("  COURSE VIDEO IMPORT E2E TESTS")
    print("=" * 60)

    # 1. Setup user
    suffix = uuid.uuid4().hex[:8]
    user_id, token = create_user_and_token(suffix)
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Created user: {user_id[:8]}...")

    # 2. Trigger Course Video Import API
    print("  POST /api/v1/course-video/import...")
    payload = {"video_url": "https://www.youtube.com/watch?v=rfscVS0vtbw"}
    resp = client.post("/api/v1/course-video/import", headers=headers, json=payload)
    
    assert resp.status_code == 201, f"Import endpoint failed: {resp.text}"
    import_data = resp.json()
    roadmap_id = import_data["roadmap_id"]
    print(f"  Import started! Roadmap ID: {roadmap_id}")
    
    assert import_data["status"] == "importing"
    assert import_data["title"] == MOCK_METADATA["title"]

    # 3. Fetch Roadmap Details and verify database records
    # Since FastAPI BackgroundTasks execute synchronously when calling via TestClient,
    # the background pipeline should have run and finished.
    print("  Fetching roadmap detail and verifying database records...")
    db = next(get_db())
    try:
        roadmap = db.query(Roadmap).filter(Roadmap.id == uuid.UUID(roadmap_id)).first()
        assert roadmap is not None
        assert roadmap.status == RoadmapStatus.READY, f"Roadmap status should be ready, got: {roadmap.status}"
        assert roadmap.total_videos == 1, f"Expected total_videos to be 1, got: {roadmap.total_videos}"
        
        # Verify total video rows in database (1 main video + 3 segment videos = 4)
        db_videos = db.query(Video).filter(Video.roadmap_id == roadmap.id).all()
        assert len(db_videos) == 4, f"Expected 4 total video rows in DB, got {len(db_videos)}"
        
        main_videos = [v for v in db_videos if not v.is_segment]
        segment_videos = [v for v in db_videos if v.is_segment]
        assert len(main_videos) == 1, f"Expected 1 main video, got {len(main_videos)}"
        assert len(segment_videos) == 3, f"Expected 3 segment videos, got {len(segment_videos)}"
        
        # Verify Modules
        modules = db.query(Module).filter(Module.roadmap_id == roadmap.id).order_by(Module.position).all()
        assert len(modules) == 3, f"Expected 3 modules, got: {len(modules)}"
        
        expected_starts = [0, 600, 1200]
        expected_names = [m["name"] for m in MOCK_CURRICULUM]
        
        for idx, mod in enumerate(modules):
            print(f"    Module {idx}: name='{mod.name}' start={mod.module_start_time} url='{mod.module_youtube_url}'")
            assert mod.name == expected_names[idx]
            assert mod.module_start_time == expected_starts[idx]
            assert mod.module_youtube_url == f"https://www.youtube.com/watch?v=rfscVS0vtbw&t={expected_starts[idx]}s"
            
            # Verify module video relationship
            assert len(mod.videos) == 1
            video_seg = mod.videos[0]
            assert video_seg.title == mod.name
            assert video_seg.youtube_id == "rfscVS0vtbw"
            assert video_seg.is_segment is True, "Module video should be marked as a segment"
            assert video_seg.ai_notes_status == AINotesStatus.DONE
            
            # Parse sliced transcript
            transcript_entries = json.loads(video_seg.transcript_text)
            assert isinstance(transcript_entries, list)
            assert len(transcript_entries) > 0
            
            # Verify timestamps fall within modules boundaries
            end_boundary = expected_starts[idx + 1] if idx < len(modules) - 1 else 1800
            for entry in transcript_entries:
                assert expected_starts[idx] <= entry["start"] < end_boundary

        print("  Database verification: PASSED.")

        # 4. Test Semantic Search within this course video
        print("\n  Searching inside course video for OOP concepts...")
        resp = client.post("/api/v1/search", headers=headers, json={
            "roadmap_id": roadmap_id,
            "query": "Where is class instantiation or object oriented programming discussed?"
        })
        assert resp.status_code == 200, f"Search failed: {resp.text}"
        results = resp.json()["results"]
        assert len(results) > 0, "No search results returned"
        
        first_match = results[0]
        print(f"    Top Match: '{first_match['video_title']}' (Score: {first_match['similarity_score']})")
        print(f"    Module Name: '{first_match['module_name']}'")
        print(f"    Source Type: '{first_match['source_type']}'")
        print(f"    Start Time: {first_match['start_time']}")
        print(f"    Matched Snippet: {first_match['matched_snippet']}")

        assert first_match["module_name"] == "Object-Oriented Programming in Python"
        assert first_match["start_time"] == 1200.0, f"Expected start time 1200.0, got {first_match['start_time']}"
        assert first_match["source_type"] == "transcript"

        print("  Semantic Search verification: PASSED.")

    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  ALL COURSE VIDEO IMPORT E2E TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

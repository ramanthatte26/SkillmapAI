"""
SkillMap AI — Semantic Search Integration Test
Tests the search schemas, services, indexing pipeline, and /api/v1/search endpoint end-to-end.
Run from backend/ directory: venv\\Scripts\\python test_search_e2e.py
"""

import json
import os
import uuid
import logging
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
logger = logging.getLogger("test_search_e2e")

client = TestClient(app)


def create_user_and_token(suffix: str) -> tuple[str, str]:
    resp = client.post("/api/v1/auth/register", json={
        "email": f"search_{suffix}@example.com",
        "username": f"searchuser{suffix}",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    data = resp.json()
    return data["user"]["id"], data["access_token"]


def seed_roadmap_data(user_id: str) -> tuple[str, list[str]]:
    """Seed a roadmap with 3 concept-specific videos."""
    db = next(get_db())
    try:
        # 1. Create Roadmap
        roadmap = Roadmap(
            user_id=uuid.UUID(user_id),
            title="Python Advanced Concepts",
            description="Master complex programming concepts in Python.",
            playlist_url="https://www.youtube.com/playlist?list=PL_search_test",
            playlist_id="PL_search_test",
            total_videos=3,
            completed_videos=0,
            status=RoadmapStatus.ACTIVE,
        )
        db.add(roadmap)
        db.flush()

        # 2. Create Videos
        v1 = Video(
            roadmap_id=roadmap.id,
            youtube_id="vid_recur_11",
            title="Introduction to Recursion",
            description="Recursion is a programming technique where a function calls itself. Learn about base cases, stack overflow, and recursive call trees.",
            duration_seconds=600,
            position=0,
            ai_notes=json.dumps({
                "summary": "This video covers the basics of recursion, explaining how recursive functions break down problems until they hit base cases.",
                "key_concepts": ["Recursive call", "Base case", "Stack overflow"],
                "important_terms": ["Call stack", "Call frame", "Activation record"],
                "interview_questions": ["What is stack overflow and how do you prevent it in recursion?"]
            }),
            ai_notes_status=AINotesStatus.DONE,
        )

        v2 = Video(
            roadmap_id=roadmap.id,
            youtube_id="vid_const_22",
            title="Constructors and Objects",
            description="A constructor is a special class method that initializes objects. Learn about __init__ in Python.",
            duration_seconds=450,
            position=1,
            ai_notes=json.dumps({
                "summary": "This video explains constructors, instance instantiation, self parameter, and basic OOP principles.",
                "key_concepts": ["Class initialization", "__init__ method", "Instantiation"],
                "important_terms": ["Constructor", "Instance attributes", "Self reference"],
                "interview_questions": ["What is the purpose of __init__ in Python classes?"]
            }),
            ai_notes_status=AINotesStatus.DONE,
        )

        v3 = Video(
            roadmap_id=roadmap.id,
            youtube_id="vid_dict_33",
            title="Mastering Dictionaries",
            description="Dictionaries in Python are key-value stores. Learn about keys, values, hash maps, and performance.",
            duration_seconds=500,
            position=2,
            ai_notes=json.dumps({
                "summary": "Deep dive into dict creation, item lookup, time complexity, and internal hash table representation.",
                "key_concepts": ["Key-value association", "Hash table", "Lookup time complexity"],
                "important_terms": ["Hashing", "Hash collision", "dict methods"],
                "interview_questions": ["What is the average time complexity of a key lookup in a dictionary?"]
            }),
            ai_notes_status=AINotesStatus.DONE,
        )

        db.add_all([v1, v2, v3])
        db.flush()

        # 3. Create Modules and associate videos
        module = Module(
            roadmap_id=roadmap.id,
            name="Core Software Engineering Concepts",
            description="Important topics for tech interviews.",
            position=0
        )
        db.add(module)
        db.flush()

        mv1 = ModuleVideo(module_id=module.id, video_id=v1.id, position=0)
        mv2 = ModuleVideo(module_id=module.id, video_id=v2.id, position=1)
        mv3 = ModuleVideo(module_id=module.id, video_id=v3.id, position=2)
        db.add_all([mv1, mv2, mv3])

        db.commit()
        return str(roadmap.id), [str(v1.id), str(v2.id), str(v3.id)]
    finally:
        db.close()


def run():
    print("\n" + "=" * 60)
    print("  SEMANTIC SEARCH E2E TESTS")
    print("=" * 60)

    # 1. Setup User and Roadmap
    suffix = uuid.uuid4().hex[:8]
    user_id, token = create_user_and_token(suffix)
    headers = {"Authorization": f"Bearer {token}"}
    roadmap_id, video_ids = seed_roadmap_data(user_id)
    
    print(f"  Seeded user={user_id[:8]}..., roadmap={roadmap_id[:8]}...")
    print(f"  Seeded video IDs: {[v[:8] for v in video_ids]}")

    # 2. Run Indexing manually (simulating the indexing trigger)
    print("  Running semantic indexing for roadmap...")
    db = next(get_db())
    try:
        search_service = SearchService()
        search_service.index_roadmap(uuid.UUID(roadmap_id), db)
    finally:
        db.close()
    print("  Indexing completed successfully.")

    # 3. Test API Search for 'recursion'
    print("\n  [Test 1] Searching for 'recursion'...")
    resp = client.post("/api/v1/search", headers=headers, json={
        "roadmap_id": roadmap_id,
        "query": "Where is recursion explained?"
    })
    assert resp.status_code == 200, f"Search failed: {resp.text}"
    results = resp.json()["results"]
    assert len(results) > 0, "No results returned"
    
    # First result should be the Recursion video
    first_match = results[0]
    print(f"    Top Match: '{first_match['video_title']}' (Score: {first_match['similarity_score']})")
    print(f"    Preview: {first_match['matched_content_preview']}")
    assert first_match["video_id"] == video_ids[0], f"Expected recursion video, got {first_match['video_title']}"
    assert "recursion" in first_match["matched_content_preview"].lower(), "Preview missing query terms"
    assert first_match["module_name"] == "Core Software Engineering Concepts", "Module name mismatch"
    print("  [Test 1] Passed.")

    # 4. Test API Search for 'constructor'
    print("\n  [Test 2] Searching for 'constructor'...")
    resp = client.post("/api/v1/search", headers=headers, json={
        "roadmap_id": roadmap_id,
        "query": "Which video teaches constructors?"
    })
    assert resp.status_code == 200, f"Search failed: {resp.text}"
    results = resp.json()["results"]
    assert len(results) > 0, "No results returned"
    first_match = results[0]
    print(f"    Top Match: '{first_match['video_title']}' (Score: {first_match['similarity_score']})")
    assert first_match["video_id"] == video_ids[1], f"Expected constructor video, got {first_match['video_title']}"
    print("  [Test 2] Passed.")

    # 5. Test API Search for 'dictionaries'
    print("\n  [Test 3] Searching for 'dictionaries'...")
    resp = client.post("/api/v1/search", headers=headers, json={
        "roadmap_id": roadmap_id,
        "query": "Where are Python dictionaries discussed?"
    })
    assert resp.status_code == 200, f"Search failed: {resp.text}"
    results = resp.json()["results"]
    assert len(results) > 0, "No results returned"
    first_match = results[0]
    print(f"    Top Match: '{first_match['video_title']}' (Score: {first_match['similarity_score']})")
    assert first_match["video_id"] == video_ids[2], f"Expected dictionary video, got {first_match['video_title']}"
    print("  [Test 3] Passed.")

    # 6. Test Security - Another user searching the roadmap -> 403 Forbidden
    print("\n  [Test 4] Verifying ownership authentication...")
    _, other_token = create_user_and_token(uuid.uuid4().hex[:8])
    other_headers = {"Authorization": f"Bearer {other_token}"}
    resp = client.post("/api/v1/search", headers=other_headers, json={
        "roadmap_id": roadmap_id,
        "query": "Where is recursion explained?"
    })
    assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}: {resp.text}"
    print("  [Test 4] Passed (403 Forbidden returned correctly for unauthorized user).")

    # 7. Test Validation - Empty query -> 422 Unprocessable Entity
    print("\n  [Test 5] Verifying validation checks...")
    resp = client.post("/api/v1/search", headers=headers, json={
        "roadmap_id": roadmap_id,
        "query": ""
    })
    assert resp.status_code == 422, f"Expected 422 validation error, got {resp.status_code}"
    print("  [Test 5] Passed (422 Unprocessable Entity returned for empty query).")

    # 8. Test Not Found Roadmap -> 404 Not Found
    print("\n  [Test 6] Verifying roadmap not found check...")
    fake_roadmap_id = str(uuid.uuid4())
    resp = client.post("/api/v1/search", headers=headers, json={
        "roadmap_id": fake_roadmap_id,
        "query": "Where is recursion explained?"
    })
    assert resp.status_code == 404, f"Expected 404 Not Found, got {resp.status_code}"
    print("  [Test 6] Passed (404 Not Found returned for fake roadmap).")

    print("\n" + "=" * 60)
    print("  ALL SEMANTIC SEARCH E2E TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run()

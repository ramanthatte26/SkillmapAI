"""
SkillMap AI — Full E2E Test: Roadmap Retrieval + Progress Tracking
"""
import sys, os, json
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=True)

def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def show(label, r):
    print(f"  Status : {r.status_code}")
    body = r.json()
    print(f"  Body   : {json.dumps(body, indent=4, default=str)}")
    return body

# ── Login as existing testuser ────────────────────────────────────
sep("STEP 1: Login")
import time
ts = int(time.time())
r = client.post("/api/v1/auth/register", json={
    "email": f"tester{ts}@skillmap.ai",
    "username": f"tester{ts}",
    "password": "TestPass123"
})
data = show("Register", r)
assert r.status_code == 201
token = data["access_token"]
user_id = data["user"]["id"]
HEADERS = {"Authorization": f"Bearer {token}"}
print(f"\n  Logged in as: {data['user']['username']}")

# ── Import the Python Tutorials playlist ─────────────────────────
sep("STEP 2: Import Playlist")
r = client.post("/api/v1/roadmaps/import", headers=HEADERS, json={
    "playlist_url": "https://www.youtube.com/playlist?list=PLWKjhJtqVAbnqBxcdjVGgT3uVR10bzTEB"
})
import_data = show("Import", r)
assert r.status_code == 201
roadmap_id = import_data["roadmap_id"]
print(f"\n  Roadmap ID: {roadmap_id}")

# ── GET /roadmaps — list ──────────────────────────────────────────
sep("STEP 3: List Roadmaps")
r = client.get("/api/v1/roadmaps", headers=HEADERS)
list_data = show("List Roadmaps", r)
assert r.status_code == 200
assert len(list_data) >= 1
print(f"\n  Total roadmaps returned: {len(list_data)}")
print(f"  First roadmap title: {list_data[0]['title']}")
print(f"  Completion: {list_data[0]['completed_videos']}/{list_data[0]['total_videos']} ({list_data[0]['completion_percentage']}%)")

# ── GET /roadmaps/{id} — detail ───────────────────────────────────
sep("STEP 4: Roadmap Detail")
r = client.get(f"/api/v1/roadmaps/{roadmap_id}", headers=HEADERS)
assert r.status_code == 200
detail = r.json()
print(f"  Status       : {r.status_code}")
print(f"  Title        : {detail['title']}")
print(f"  Status       : {detail['status']}")
print(f"  Total Videos : {detail['total_videos']}")
print(f"  Completion   : {detail['completion_percentage']}%")
print(f"\n  Videos (first 5 of {len(detail['videos'])}):")
for v in detail["videos"][:5]:
    print(f"    [{v['position']+1:>2}] {v['title'][:55]:<56} | {v['youtube_id']}")

video_id_1 = detail["videos"][0]["id"]
video_id_2 = detail["videos"][1]["id"]
video_id_3 = detail["videos"][2]["id"]

# ── PUT /progress/video/{id} — mark 3 videos complete ────────────
sep("STEP 5: Mark Videos as Completed")
for i, vid_id in enumerate([video_id_1, video_id_2, video_id_3], 1):
    r = client.put(f"/api/v1/progress/video/{vid_id}", headers=HEADERS, json={
        "is_completed": True,
        "watch_time_seconds": 3600 * i,
        "user_notes": f"Great video #{i}! Really learned a lot."
    })
    assert r.status_code == 200, f"Failed on video {i}: {r.text}"
    p = r.json()
    print(f"  Video {i} marked complete | completed_at: {p['completed_at'][:19] if p['completed_at'] else 'None'}")

# ── PUT /progress/video/{id} — un-mark video 2 ───────────────────
sep("STEP 6: Un-mark Video 2 (idempotency check)")
r = client.put(f"/api/v1/progress/video/{video_id_2}", headers=HEADERS, json={
    "is_completed": False,
    "watch_time_seconds": 1800,
})
assert r.status_code == 200
p = r.json()
print(f"  Video 2 un-marked | is_completed={p['is_completed']} | completed_at={p['completed_at']}")

# ── GET /progress/roadmap/{id} — stats ────────────────────────────
sep("STEP 7: Progress Statistics")
r = client.get(f"/api/v1/progress/roadmap/{roadmap_id}", headers=HEADERS)
assert r.status_code == 200
stats = show("Stats", r)
print(f"\n  {stats['completed_videos']} of {stats['total_videos']} videos complete ({stats['completion_percentage']}%)")
print(f"  Remaining: {stats['remaining_videos']} videos")

# ── Security: try accessing another user's roadmap ─────────────────
sep("STEP 8: Security — unauthorized roadmap access")
r2 = client.post("/api/v1/auth/register", json={
    "email": f"hacker{ts}@evil.ai",
    "username": f"hacker{ts}",
    "password": "HackPass123"
})
hacker_token = r2.json()["access_token"]
HACKER_HEADERS = {"Authorization": f"Bearer {hacker_token}"}

r = client.get(f"/api/v1/roadmaps/{roadmap_id}", headers=HACKER_HEADERS)
print(f"  Hacker GET /roadmaps/{roadmap_id[:8]}... -> {r.status_code} {r.json()['detail']}")
assert r.status_code == 403, f"Expected 403 but got {r.status_code}"

r = client.put(f"/api/v1/progress/video/{video_id_1}", headers=HACKER_HEADERS, json={"is_completed": True})
print(f"  Hacker PUT /progress/video/... -> {r.status_code} {r.json()['detail']}")
assert r.status_code == 403, f"Expected 403 but got {r.status_code}"

sep("ALL TESTS PASSED")
print("  Roadmap list       : OK")
print("  Roadmap detail     : OK")
print("  Progress upsert    : OK")
print("  Progress un-mark   : OK")
print("  Progress stats     : OK")
print("  Ownership security : OK")

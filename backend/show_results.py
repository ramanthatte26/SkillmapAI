import sys; sys.path.insert(0, '.')
from app.database import SessionLocal
from app.models.roadmap import Roadmap
from app.models.video import Video

db = SessionLocal()
roadmap = db.query(Roadmap).order_by(Roadmap.created_at.desc()).first()

print("=" * 80)
print("ROADMAP DETAILS")
print("=" * 80)
print(f"Title       : {roadmap.title}")
print(f"Roadmap ID  : {roadmap.id}")
print(f"Playlist ID : {roadmap.playlist_id}")
print(f"Status      : {roadmap.status.value}")
print(f"Total Videos: {roadmap.total_videos}")
print(f"Thumbnail   : {roadmap.thumbnail_url}")
print(f"Created At  : {roadmap.created_at}")
print()
print("=" * 80)
print("VIDEOS IMPORTED")
print("=" * 80)
header = "{:<4} {:<65} {:<14}".format("No.", "Title", "YouTube ID")
print(header)
print("-" * 85)

videos = db.query(Video).filter(Video.roadmap_id == roadmap.id).order_by(Video.position).all()
for v in videos:
    row = "{:<4} {:<65} {:<14}".format(v.position + 1, v.title[:63], v.youtube_id)
    print(row)

print("-" * 85)
print(f"Total: {len(videos)} videos stored in DB")
db.close()

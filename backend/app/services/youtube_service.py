"""
SkillMap AI — YouTube Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles all interaction with the YouTube Data API v3.

Responsibilities:
  1. Extract and validate playlist IDs from various YouTube URL formats
  2. Fetch playlist metadata (title, description, thumbnail)
  3. Fetch all videos in a playlist with full pagination support
  4. Parse ISO 8601 duration strings into integer seconds
  5. Create Roadmap + Video records in the database
  6. Provide structured error handling for API failures

API quota notes (YouTube Data API v3):
  - Default quota: 10,000 units/day
  - playlistItems.list costs 1 unit per call (max 50 items/page)
  - playlists.list costs 1 unit per call
  - A 500-video playlist costs ~11 units total (1 + ceil(500/50))

Design pattern:
  This service is a pure Python class instantiated with an httpx.Client.
  No FastAPI dependencies inside the service — it's independently testable.
  The router layer handles dependency injection and HTTP concerns.
"""

import logging
import uuid
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.orm import Session
from youtube_transcript_api import YouTubeTranscriptApi

from app.config import get_settings
from app.models.roadmap import Roadmap, RoadmapStatus
from app.models.video import Video, AINotesStatus
from app.schemas.roadmap import RoadmapImportResponse
from app.utils.exceptions import BadRequestException, NotFoundException

# ── Module logger ─────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_RESULTS_PER_PAGE = 50          # YouTube API maximum per page
MAX_VIDEOS_LIMIT = 500             # Safety cap: prevent runaway imports
ISO_8601_DURATION_RE = re.compile(
    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
    re.IGNORECASE,
)

# Regex patterns that match a playlist ID in various YouTube URL forms
PLAYLIST_ID_RE = re.compile(r"[?&]list=([A-Za-z0-9_-]+)")


class YouTubeService:
    """
    Encapsulates all YouTube Data API v3 interactions.

    Usage (inside a FastAPI dependency or router):
        service = YouTubeService()
        roadmap = service.import_playlist(
            playlist_url=url,
            user_id=current_user.id,
            db=db,
        )
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.youtube_api_key
        # Shared httpx client with timeout and retry-friendly defaults
        self._client = httpx.Client(
            base_url=YOUTUBE_API_BASE,
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            headers={"Accept": "application/json"},
        )

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def import_playlist(
        self,
        playlist_url: str,
        user_id: object,  # uuid.UUID
        db: Session,
    ) -> RoadmapImportResponse:
        """
        Creates a skeleton Roadmap in the database with status = IMPORTING.
        The actual video ingestion, module generation, note generation, and indexing
        run asynchronously in the background.
        """
        self._assert_api_key_configured()

        # Step 1 — Extract playlist ID
        playlist_id = self._extract_playlist_id(playlist_url)
        logger.info("Starting skeleton import for playlist_id=%s user_id=%s", playlist_id, user_id)

        # Step 2 — Fetch playlist metadata synchronously (helps check if it exists early)
        metadata = self._fetch_playlist_metadata(playlist_id)
        logger.info("Fetched metadata: title=%r", metadata["title"])

        # Step 3 — Persist skeleton roadmap (IMPORTING state, total_videos=0 initially)
        roadmap = Roadmap(
            user_id=user_id,
            title=metadata["title"],
            description=metadata.get("description"),
            playlist_url=playlist_url,
            playlist_id=playlist_id,
            thumbnail_url=metadata.get("thumbnail_url"),
            total_videos=0,
            completed_videos=0,
            status=RoadmapStatus.IMPORTING,
        )
        db.add(roadmap)
        db.commit()
        db.refresh(roadmap)
        logger.info("Skeleton roadmap created: id=%s title=%r", roadmap.id, roadmap.title)

        return RoadmapImportResponse(
            roadmap_id=roadmap.id,
            title=roadmap.title,
            total_videos=0,
            status=roadmap.status,
            message="Playlist import started in the background."
        )

    # ─────────────────────────────────────────────────────────────
    # URL Parsing
    # ─────────────────────────────────────────────────────────────

    def _extract_playlist_id(self, url: str) -> str:
        """
        Extract the playlist ID from any YouTube URL variant.

        Supported URL formats:
          - https://www.youtube.com/playlist?list=PLxxxxx
          - https://youtube.com/playlist?list=PLxxxxx
          - https://www.youtube.com/watch?v=xxx&list=PLxxxxx

        Returns:
          The raw playlist ID string (e.g. "PLrAXtmErZgOeiKm4sgNOknc2igCU6Uura").

        Raises:
          BadRequestException: If no playlist ID can be found in the URL.
        """
        match = PLAYLIST_ID_RE.search(url)
        if not match:
            raise BadRequestException(
                "Could not extract a playlist ID from the provided URL. "
                "Make sure the URL contains '?list=...' or '&list=...'."
            )
        playlist_id = match.group(1)
        logger.debug("Extracted playlist_id=%r from url=%r", playlist_id, url)
        return playlist_id

    def extract_video_id(self, url: str) -> str:
        """
        Extract the video ID from a YouTube watch or share URL.

        Supported URL formats:
          - https://www.youtube.com/watch?v=dQw4w9WgXcQ
          - https://youtube.com/watch?v=dQw4w9WgXcQ
          - https://youtu.be/dQw4w9WgXcQ
          - https://www.youtube.com/embed/dQw4w9WgXcQ
        """
        parsed = urlparse(url)
        if parsed.netloc == "youtu.be":
            return parsed.path.lstrip("/")
        if parsed.path in ("/watch", "/watch/"):
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2]
        
        match = re.search(r"(?:v=|\/embed\/|\/101\/|\/v\/|youtu\.be\/|\/vi\/)([A-Za-z0-9_-]{11})", url)
        if match:
            return match.group(1)
        raise BadRequestException("Could not extract a valid YouTube Video ID from the URL.")

    # ─────────────────────────────────────────────────────────────
    # YouTube API — Playlist Metadata
    # ─────────────────────────────────────────────────────────────

    def _fetch_playlist_metadata(self, playlist_id: str) -> dict[str, Any]:
        """
        Fetch the playlist's title, description, and thumbnail.

        Calls:
            GET /playlists?part=snippet&id={playlist_id}&key={api_key}

        Returns:
            Dict with keys: title, description, thumbnail_url.

        Raises:
            NotFoundException:   Playlist not found or is private/deleted.
            BadRequestException: API quota exceeded or rate limit hit.
        """
        logger.debug("Fetching playlist metadata for playlist_id=%s", playlist_id)

        response = self._get(
            "/playlists",
            params={
                "part": "snippet",
                "id": playlist_id,
                "maxResults": 1,
                "key": self.api_key,
            },
        )
        data = response.json()

        items = data.get("items", [])
        if not items:
            raise NotFoundException(
                f"Playlist '{playlist_id}' was not found. "
                "It may be private, deleted, or the ID is incorrect."
            )

        snippet = items[0]["snippet"]
        thumbnail_url = self._best_thumbnail(snippet.get("thumbnails", {}))

        return {
            "title": snippet.get("title", "Untitled Playlist"),
            "description": snippet.get("description", ""),
            "thumbnail_url": thumbnail_url,
        }

    def fetch_video_metadata(self, video_id: str) -> dict[str, Any]:
        """
        Fetch a video's title, description, thumbnail, and duration.
        Calls:
            GET /videos?part=snippet,contentDetails&id={video_id}&key={api_key}
        """
        self._assert_api_key_configured()
        logger.debug("Fetching video metadata for video_id=%s", video_id)

        response = self._get(
            "/videos",
            params={
                "part": "snippet,contentDetails",
                "id": video_id,
                "key": self.api_key,
            },
        )
        data = response.json()

        items = data.get("items", [])
        if not items:
            raise NotFoundException(
                f"Video '{video_id}' was not found. "
                "It may be private, deleted, or the ID is incorrect."
            )

        snippet = items[0]["snippet"]
        content_details = items[0].get("contentDetails", {})
        
        thumbnail_url = self._best_thumbnail(snippet.get("thumbnails", {}))
        duration_seconds = self._parse_iso8601_duration(content_details.get("duration", ""))

        return {
            "youtube_id": video_id,
            "title": snippet.get("title", "Untitled Video"),
            "description": snippet.get("description", ""),
            "thumbnail_url": thumbnail_url,
            "duration_seconds": duration_seconds,
        }

    # ─────────────────────────────────────────────────────────────
    # YouTube API — Playlist Videos (with pagination)
    # ─────────────────────────────────────────────────────────────

    def _fetch_all_playlist_videos(self, playlist_id: str) -> list[dict[str, Any]]:
        """
        Fetch all videos in a playlist, handling multi-page responses.

        YouTube returns a maximum of 50 items per page. This method
        follows nextPageToken links until all pages are exhausted.

        Calls:
            GET /playlistItems?part=snippet,contentDetails&playlistId=...

        Returns:
            List of video dicts sorted by position, each containing:
              youtube_id, title, description, thumbnail_url,
              duration_seconds, position.

        Raises:
            NotFoundException:   Playlist not accessible.
            BadRequestException: Quota exceeded.
        """
        videos: list[dict[str, Any]] = []
        next_page_token: str | None = None
        page_number = 0

        while True:
            page_number += 1
            logger.debug(
                "Fetching page %d of playlist items for playlist_id=%s",
                page_number, playlist_id,
            )

            params: dict[str, Any] = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": MAX_RESULTS_PER_PAGE,
                "key": self.api_key,
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            response = self._get("/playlistItems", params=params)
            data = response.json()

            items = data.get("items", [])
            for item in items:
                parsed = self._parse_playlist_item(item)
                if parsed:
                    videos.append(parsed)

            # Safety cap — prevent importing enormous playlists
            if len(videos) >= MAX_VIDEOS_LIMIT:
                logger.warning(
                    "Playlist %s has >%d videos. Capping at %d.",
                    playlist_id, MAX_VIDEOS_LIMIT, MAX_VIDEOS_LIMIT,
                )
                videos = videos[:MAX_VIDEOS_LIMIT]
                break

            # Follow pagination
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break  # All pages consumed

        # Re-assign positions to be 0-indexed and consecutive
        # (YouTube positions can have gaps for deleted/private videos)
        for idx, video in enumerate(videos):
            video["position"] = idx

        logger.debug("Total videos fetched: %d", len(videos))
        return videos

    def _parse_playlist_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse a single playlistItems API response item into our internal shape.

        YouTube includes private/deleted videos as items with no video ID.
        These are filtered out by returning None.

        Returns:
            Parsed video dict or None if the video is unavailable.
        """
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})

        youtube_id = (
            snippet.get("resourceId", {}).get("videoId")
            or content_details.get("videoId")
        )

        # Filter out private/deleted videos — they appear as items
        # with title "Private video" or "Deleted video" and no video ID
        if not youtube_id or snippet.get("title") in ("Private video", "Deleted video"):
            logger.debug("Skipping unavailable video: %s", snippet.get("title"))
            return None

        thumbnail_url = self._best_thumbnail(snippet.get("thumbnails", {}))

        return {
            "youtube_id": youtube_id,
            "title": snippet.get("title", "Untitled Video"),
            "description": snippet.get("description", ""),
            "thumbnail_url": thumbnail_url,
            "duration_seconds": None,   # Duration requires a separate videos.list call
            "position": snippet.get("position", 0),
        }

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, Any]) -> httpx.Response:
        """
        Execute a GET request against the YouTube API with centralised
        error handling for all HTTP and API-level errors.

        Args:
            path:   API path relative to YOUTUBE_API_BASE.
            params: Query parameters (api key should always be included).

        Returns:
            httpx.Response on success (2xx status).

        Raises:
            BadRequestException: On 400 (bad request), 403 (quota exceeded),
                                  429 (rate limit), 5xx (server error).
            NotFoundException:   On 404.
        """
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException:
            logger.error("YouTube API request timed out: path=%s", path)
            raise BadRequestException(
                "The YouTube API did not respond in time. Please try again."
            )
        except httpx.RequestError as exc:
            logger.error("YouTube API network error: %s", exc)
            raise BadRequestException(
                f"Could not reach the YouTube API: {exc}"
            )

        self._raise_for_youtube_status(response, path)
        return response

    def _raise_for_youtube_status(self, response: httpx.Response, path: str) -> None:
        """
        Translate YouTube API HTTP errors into domain exceptions.

        YouTube error codes:
          400 → Bad request (e.g. invalid parameters)
          403 → Quota exceeded or access denied
          404 → Resource not found
          429 → Rate limited (too many requests per second)
          5xx → YouTube server error
        """
        status_code = response.status_code

        if status_code == 200:
            return

        # Try to extract YouTube's error message for better debugging
        try:
            error_body = response.json()
            yt_message = (
                error_body.get("error", {}).get("message", "Unknown error")
            )
            yt_reason = (
                error_body.get("error", {})
                .get("errors", [{}])[0]
                .get("reason", "")
            )
        except Exception:
            yt_message = response.text[:200]
            yt_reason = ""

        logger.error(
            "YouTube API error: status=%d path=%s message=%r reason=%r",
            status_code, path, yt_message, yt_reason,
        )

        if status_code == 400:
            raise BadRequestException(f"YouTube API: Bad request — {yt_message}")

        if status_code == 403:
            if "quotaExceeded" in yt_reason or "dailyLimitExceeded" in yt_reason:
                raise BadRequestException(
                    "YouTube API daily quota exceeded. "
                    "Please try again after midnight Pacific Time (PT)."
                )
            raise BadRequestException(
                f"YouTube API access denied — {yt_message}. "
                "Check that your API key is valid and has YouTube Data API v3 enabled."
            )

        if status_code == 404:
            raise NotFoundException("The requested YouTube resource was not found.")

        if status_code == 429:
            raise BadRequestException(
                "YouTube API rate limit reached. Please wait a moment and try again."
            )

        if status_code >= 500:
            raise BadRequestException(
                f"YouTube is experiencing server issues (HTTP {status_code}). "
                "Please try again later."
            )

        # Catch-all for unexpected status codes
        raise BadRequestException(
            f"Unexpected YouTube API response: HTTP {status_code} — {yt_message}"
        )

    @staticmethod
    def _best_thumbnail(thumbnails: dict[str, Any]) -> str | None:
        """
        Select the highest-quality available thumbnail URL.

        YouTube provides thumbnails at these keys (highest to lowest quality):
          maxres → standard → high → medium → default

        Returns the first available URL or None if no thumbnails exist.
        """
        for quality in ("maxres", "standard", "high", "medium", "default"):
            thumb = thumbnails.get(quality)
            if thumb and thumb.get("url"):
                return thumb["url"]
        return None

    @staticmethod
    def _parse_iso8601_duration(duration: str) -> int:
        """
        Convert an ISO 8601 duration string to total seconds.

        Examples:
          "PT1H23M45S" → 5025
          "PT5M30S"    → 330
          "PT45S"      → 45
          "PT0S"       → 0

        Returns 0 for any unparseable duration string.
        """
        if not duration:
            return 0
        match = ISO_8601_DURATION_RE.match(duration)
        if not match:
            logger.debug("Could not parse ISO 8601 duration: %r", duration)
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    def _assert_api_key_configured(self) -> None:
        """
        Raise early if the YouTube API key is missing.
        Much better than letting it fail with a cryptic 400 from YouTube.
        """
        if not self.api_key:
            raise BadRequestException(
                "YouTube API key is not configured. "
                "Set YOUTUBE_API_KEY in your .env file."
            )

    def __del__(self) -> None:
        """Close the httpx client when the service is garbage collected."""
        try:
            self._client.close()
        except Exception:
            pass


def run_background_pipeline(roadmap_id: uuid.UUID, user_id: uuid.UUID):
    """
    Asynchronous background pipeline for video ingestion, module grouping,
    parallel notes generation, search indexing, and initial insights compilation.
    """
    from app.database import SessionLocal
    from app.services.youtube_service import YouTubeService
    from app.services.module_service import ModuleService
    from app.services.search_service import SearchService
    from app.services.insights_service import InsightsService
    from app.models.roadmap import Roadmap, RoadmapStatus
    from app.models.video import Video, AINotesStatus
    import json
    from concurrent.futures import ThreadPoolExecutor

    logger.info("Starting background pipeline for roadmap %s", roadmap_id)
    db = SessionLocal()
    try:
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.error("Background pipeline: Roadmap %s not found in DB", roadmap_id)
            return

        # ── Step 1: Import Videos & Transcripts ───────────────────
        # Status is already IMPORTING
        yt_service = YouTubeService()
        logger.info("Background pipeline Step 1: Ingesting videos for roadmap %s", roadmap_id)
        
        raw_videos = yt_service._fetch_all_playlist_videos(roadmap.playlist_id)
        logger.info("Background pipeline: Fetched %d videos from playlist", len(raw_videos))

        # Update roadmap total videos count
        roadmap.total_videos = len(raw_videos)
        db.flush()

        # Fetch transcripts and construct Video rows
        video_objects = []
        for v in raw_videos:
            youtube_id = v["youtube_id"]
            transcript_text = None
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                logger.info("Background pipeline: Fetching transcript for youtube_id=%s", youtube_id)
                transcript_list = YouTubeTranscriptApi().fetch(youtube_id)
                transcript_text = " ".join([t.text for t in transcript_list])
            except Exception as exc:
                logger.warning("Background pipeline: Could not fetch transcript for youtube_id=%s: %s", youtube_id, exc)

            video_objects.append(
                Video(
                    roadmap_id=roadmap.id,
                    youtube_id=youtube_id,
                    title=v["title"],
                    description=v.get("description"),
                    thumbnail_url=v.get("thumbnail_url"),
                    duration_seconds=v.get("duration_seconds"),
                    position=v["position"],
                    ai_notes_status=AINotesStatus.PENDING,
                    transcript_text=transcript_text,
                )
            )
        db.bulk_save_objects(video_objects)
        db.commit()
        
        # Refresh roadmap and fetch videos to get database IDs
        db.refresh(roadmap)
        videos = db.query(Video).filter(Video.roadmap_id == roadmap_id).order_by(Video.position).all()

        # ── Step 2: Generate Learning Modules ─────────────────────
        logger.info("Background pipeline Step 2: Generating modules for roadmap %s", roadmap_id)
        roadmap.status = RoadmapStatus.GENERATING_MODULES
        db.commit()

        module_service = ModuleService()
        try:
            module_service.generate_and_store_modules(roadmap_id=roadmap.id, user_id=user_id, db=db)
        except Exception as exc:
            logger.error("Background pipeline: Module generation failed: %s. Using fallback.", exc)

        # ── Step 3: Generate AI Notes (in parallel) ──────────────
        logger.info("Background pipeline Step 3: Generating AI notes for roadmap %s", roadmap_id)
        roadmap.status = RoadmapStatus.GENERATING_NOTES
        db.commit()

        # Resolve module names for each video (best effort context)
        modules = module_service.get_roadmap_modules(roadmap_id=roadmap.id, user_id=user_id, db=db)
        video_to_module_name = {}
        for mod in modules:
            for mv in mod.videos:
                video_to_module_name[mv.id] = mod.name

        # Mark all videos as generating
        for video in videos:
            video.ai_notes_status = AINotesStatus.GENERATING
        db.commit()

        def fetch_notes(v_id, title, desc, trans_text):
            try:
                from app.services.ai_service import AIService
                ai = AIService()
                mod_name = video_to_module_name.get(v_id)
                notes_dict = ai.generate_video_notes(
                    video_title=title,
                    roadmap_title=roadmap.title,
                    module_name=mod_name,
                    video_description=desc,
                    transcript_text=trans_text,
                )
                return v_id, notes_dict, AINotesStatus.DONE
            except Exception as e:
                logger.error("Background notes fetch failed for video %s: %s", v_id, e)
                return v_id, None, AINotesStatus.FAILED

        # Run notes generation requests in parallel (max 5 threads)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(fetch_notes, video.id, video.title, video.description, video.transcript_text)
                for video in videos
            ]
            results = [f.result() for f in futures]

        # Save generated notes to database
        for v_id, notes_dict, note_status in results:
            video = db.query(Video).filter(Video.id == v_id).first()
            if video:
                video.ai_notes_status = note_status
                if notes_dict:
                    video.ai_notes = json.dumps(notes_dict)
                else:
                    # Fallback notes if failed
                    from app.services.ai_service import AIService
                    fallback_notes = AIService()._generate_fallback_notes(video.title, roadmap.title)
                    video.ai_notes = json.dumps(fallback_notes)
                    video.ai_notes_status = AINotesStatus.DONE
        db.commit()

        # ── Step 4: Build Search Index ────────────────────────────
        logger.info("Background pipeline Step 4: Building search index for roadmap %s", roadmap_id)
        roadmap.status = RoadmapStatus.BUILDING_SEARCH_INDEX
        db.commit()

        search_service = SearchService()
        search_service.index_roadmap(roadmap_id, db)

        # ── Step 5: Generate Initial Insights ─────────────────────
        logger.info("Background pipeline Step 5: Generating initial insights for roadmap %s", roadmap_id)
        insights_service = InsightsService()
        try:
            insights = insights_service.get_roadmap_insights(roadmap_id=roadmap.id, user_id=user_id, db=db)
            roadmap.insights_json = json.dumps(insights)
        except Exception as exc:
            logger.error("Background pipeline: Insights generation failed: %s", exc)

        # ── Step 6: Ready! ────────────────────────────────────────
        logger.info("Background pipeline finished successfully. Roadmap %s is READY", roadmap_id)
        roadmap.status = RoadmapStatus.READY
        db.commit()

    except Exception as exc:
        logger.error("Background pipeline failed for roadmap %s: %s", roadmap_id, exc)
        try:
            roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
            if roadmap:
                roadmap.status = RoadmapStatus.FAILED
                db.commit()
        except Exception as db_exc:
            logger.error("Failed to set FAILED status for roadmap %s: %s", roadmap_id, db_exc)
    finally:
        db.close()


def run_course_video_background_pipeline(
    roadmap_id: uuid.UUID,
    user_id: uuid.UUID,
    video_id: str,
    metadata: dict
):
    """
    Asynchronous background pipeline for single course video ingestion.
    """
    from app.database import SessionLocal
    from app.services.ai_service import AIService
    from app.services.search_service import SearchService
    from app.services.insights_service import InsightsService
    from app.models.roadmap import Roadmap, RoadmapStatus
    from app.models.video import Video, AINotesStatus
    from app.models.module import Module, ModuleVideo
    import json
    from concurrent.futures import ThreadPoolExecutor

    logger.info("Starting background pipeline for course video roadmap %s", roadmap_id)
    db = SessionLocal()
    try:
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.error("Background course pipeline: Roadmap %s not found in DB", roadmap_id)
            return

        # ── Step 1: Retrieve Transcript ───────────────────
        raw_transcript = []
        transcript_text_fallback = f"This course video titled '{metadata['title']}' covers various topics. No transcript was available."
        try:
            logger.info("Background course pipeline: Fetching transcript for video_id=%s", video_id)
            raw_transcript_objects = YouTubeTranscriptApi().fetch(video_id)
            raw_transcript = [
                {"text": entry.text, "start": entry.start, "duration": entry.duration}
                for entry in raw_transcript_objects
            ]
            logger.info("Background course pipeline: Retrieved %d transcript entries", len(raw_transcript))
        except Exception as exc:
            logger.warning("Background course pipeline: Could not fetch transcript: %s. Using placeholder.", exc)
            # Create a simple placeholder entry covering the whole video
            raw_transcript = [{"text": transcript_text_fallback, "start": 0.0, "duration": float(metadata["duration_seconds"] or 3600)}]

        # ── Step 2: Format Transcript & Segment Curriculum ──────
        logger.info("Background course pipeline Step 2: segmenting course curriculum")
        roadmap.status = RoadmapStatus.GENERATING_MODULES
        db.commit()

        # Format transcript into blocks
        yt_service = YouTubeService()
        formatted_transcript = format_transcript_with_timestamps(raw_transcript)
        
        # Segment curriculum using AI
        ai_service = AIService()
        course_overview, modules_def = ai_service.extract_course_curriculum(
            roadmap_title=roadmap.title,
            timestamped_transcript=formatted_transcript,
            total_duration_seconds=metadata["duration_seconds"] or 3600
        )
        logger.info("Background course pipeline: Extracted %d curriculum modules", len(modules_def))

        # Update roadmap description with the generated overview
        roadmap.description = course_overview
        db.commit()

        # Create the main original Video object
        main_video = Video(
            roadmap_id=roadmap.id,
            youtube_id=video_id,
            title=metadata["title"],
            description=metadata.get("description") or course_overview,
            thumbnail_url=metadata.get("thumbnail_url"),
            duration_seconds=metadata["duration_seconds"],
            position=0,
            ai_notes_status=AINotesStatus.DONE,
            transcript_text=json.dumps(raw_transcript),
            is_segment=False
        )
        db.add(main_video)
        db.flush()

        # ── Step 3: Create Video Segments & Modules ───────────────
        video_objects = []
        module_objects = []
        module_video_relations = []
        
        total_duration = metadata["duration_seconds"] or 3600

        for idx, m_def in enumerate(modules_def):
            start_time = m_def["start_timestamp_seconds"]
            
            # Find end time
            if idx < len(modules_def) - 1:
                end_time = modules_def[idx + 1]["start_timestamp_seconds"]
            else:
                end_time = total_duration
                
            seg_duration = max(60, end_time - start_time)
            
            # Slice transcript entries
            sliced_entries = [
                entry for entry in raw_transcript
                if start_time <= entry["start"] < end_time
            ]
            if not sliced_entries:
                sliced_entries = [{"text": m_def["description"], "start": float(start_time), "duration": float(seg_duration)}]
                
            sliced_json = json.dumps(sliced_entries)
            
            # Generate youtube deep link
            module_youtube_url = f"https://www.youtube.com/watch?v={video_id}&t={start_time}s"
            
            # 3.1 Create Video (segment) object
            video_segment = Video(
                roadmap_id=roadmap.id,
                youtube_id=video_id,
                title=m_def["name"],
                description=m_def["description"],
                thumbnail_url=metadata.get("thumbnail_url"),
                duration_seconds=seg_duration,
                position=idx,
                ai_notes_status=AINotesStatus.PENDING,
                transcript_text=sliced_json,
                is_segment=True
            )
            video_objects.append(video_segment)

            # 3.2 Create Module object
            module_obj = Module(
                roadmap_id=roadmap.id,
                name=m_def["name"],
                description=m_def["description"],
                position=idx,
                module_start_time=start_time,
                module_youtube_url=module_youtube_url
            )
            module_objects.append(module_obj)

        # Save videos and modules
        for v_seg in video_objects:
            db.add(v_seg)
        for m_obj in module_objects:
            db.add(m_obj)
        db.flush() # Populate IDs

        # Map them together
        for idx in range(len(video_objects)):
            mv = ModuleVideo(
                module_id=module_objects[idx].id,
                video_id=video_objects[idx].id,
                position=0
            )
            module_video_relations.append(mv)
            
        for mv in module_video_relations:
            db.add(mv)
            
        roadmap.total_videos = 1
        db.commit()

        # ── Step 4: Generate AI Notes (in parallel) ──────────────
        logger.info("Background course pipeline Step 4: Generating AI notes")
        roadmap.status = RoadmapStatus.GENERATING_NOTES
        db.commit()

        # Mark all segment videos as generating
        videos = db.query(Video).filter(
            Video.roadmap_id == roadmap.id,
            Video.is_segment == True
        ).order_by(Video.position).all()
        for v in videos:
            v.ai_notes_status = AINotesStatus.GENERATING
        db.commit()

        def fetch_notes(v_id, title, desc, trans_json):
            try:
                ai = AIService()
                notes_dict = ai.generate_video_notes(
                    video_title=title,
                    roadmap_title=roadmap.title,
                    module_name=title, # Module name is video segment title here
                    video_description=desc,
                    transcript_text=trans_json,
                )
                return v_id, notes_dict, AINotesStatus.DONE
            except Exception as e:
                logger.error("Background notes fetch failed for course video segment %s: %s", v_id, e)
                return v_id, None, AINotesStatus.FAILED

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(fetch_notes, video.id, video.title, video.description, video.transcript_text)
                for video in videos
            ]
            results = [f.result() for f in futures]

        for v_id, notes_dict, note_status in results:
            video = db.query(Video).filter(Video.id == v_id).first()
            if video:
                video.ai_notes_status = note_status
                if notes_dict:
                    video.ai_notes = json.dumps(notes_dict)
                else:
                    fallback_notes = AIService()._generate_fallback_notes(video.title, roadmap.title)
                    video.ai_notes = json.dumps(fallback_notes)
                    video.ai_notes_status = AINotesStatus.DONE
        db.commit()

        # ── Step 5: Build Search Index ────────────────────────────
        logger.info("Background course pipeline Step 5: Building search index")
        roadmap.status = RoadmapStatus.BUILDING_SEARCH_INDEX
        db.commit()

        search_service = SearchService()
        search_service.index_roadmap(roadmap.id, db)

        # ── Step 6: Generate Initial Insights ─────────────────────
        logger.info("Background course pipeline Step 6: Generating initial insights")
        insights_service = InsightsService()
        try:
            insights = insights_service.get_roadmap_insights(roadmap_id=roadmap.id, user_id=user_id, db=db)
            roadmap.insights_json = json.dumps(insights)
        except Exception as exc:
            logger.error("Background course pipeline: Insights generation failed: %s", exc)

        # ── Step 7: Ready! ────────────────────────────────────────
        logger.info("Background course pipeline finished successfully. Roadmap %s is READY", roadmap.id)
        roadmap.status = RoadmapStatus.READY
        db.commit()

    except Exception as exc:
        logger.error("Background course pipeline failed for roadmap %s: %s", roadmap_id, exc)
        try:
            roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
            if roadmap:
                roadmap.status = RoadmapStatus.FAILED
                db.commit()
        except Exception as db_exc:
            logger.error("Failed to set FAILED status for roadmap %s: %s", roadmap_id, db_exc)
    finally:
        db.close()


def format_transcript_with_timestamps(transcript_list: list[dict], interval_seconds: int = 60) -> str:
    """
    Groups transcript entries into blocks of interval_seconds,
    formatting each block with a timestamp [HH:MM:SS] or [MM:SS].
    """
    if not transcript_list:
        return ""
    
    blocks = []
    current_block_start = 0.0
    current_block_text = []
    
    for entry in transcript_list:
        start = entry["start"]
        text = entry["text"]
        
        if start >= current_block_start + interval_seconds:
            # Commit current block
            h = int(current_block_start // 3600)
            m = int((current_block_start % 3600) // 60)
            s = int(current_block_start % 60)
            timestamp_str = f"[{h:02d}:{m:02d}:{s:02d}]" if h > 0 else f"[{m:02d}:{s:02d}]"
            
            blocks.append(f"{timestamp_str} {' '.join(current_block_text)}")
            current_block_start = start
            current_block_text = [text]
        else:
            current_block_text.append(text)
            
    if current_block_text:
        h = int(current_block_start // 3600)
        m = int((current_block_start % 3600) // 60)
        s = int(current_block_start % 60)
        timestamp_str = f"[{h:02d}:{m:02d}:{s:02d}]" if h > 0 else f"[{m:02d}:{s:02d}]"
        blocks.append(f"{timestamp_str} {' '.join(current_block_text)}")
        
    return "\n".join(blocks)

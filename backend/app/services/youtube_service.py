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
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.orm import Session

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
        Full import pipeline: URL → DB Roadmap + Videos.

        Steps:
          1. Extract playlist ID from URL
          2. Fetch playlist metadata from YouTube
          3. Fetch all video items with pagination
          4. Persist Roadmap record (status=PROCESSING)
          5. Persist all Video records in a single bulk insert
          6. Flip roadmap status to ACTIVE
          7. Return RoadmapImportResponse

        Args:
            playlist_url: Any valid YouTube playlist URL.
            user_id:      UUID of the authenticated user.
            db:           SQLAlchemy session (injected by dependency).

        Returns:
            RoadmapImportResponse with roadmap_id, title, total_videos.

        Raises:
            BadRequestException:  If the URL contains no valid playlist ID,
                                  or the API key is not configured.
            NotFoundException:    If the playlist doesn't exist or is private.
            BadRequestException:  If YouTube returns a rate-limit (429) or
                                  quota-exceeded (403) error.
        """
        self._assert_api_key_configured()

        # Step 1 — Extract playlist ID
        playlist_id = self._extract_playlist_id(playlist_url)
        logger.info("Starting import for playlist_id=%s user_id=%s", playlist_id, user_id)

        # Step 2 — Fetch playlist metadata
        metadata = self._fetch_playlist_metadata(playlist_id)
        logger.info("Fetched metadata: title=%r", metadata["title"])

        # Step 3 — Fetch all video items
        raw_videos = self._fetch_all_playlist_videos(playlist_id)
        logger.info("Fetched %d video(s) from playlist", len(raw_videos))

        # Step 4 — Persist roadmap (PROCESSING state)
        roadmap = Roadmap(
            user_id=user_id,
            title=metadata["title"],
            description=metadata.get("description"),
            playlist_url=playlist_url,
            playlist_id=playlist_id,
            thumbnail_url=metadata.get("thumbnail_url"),
            total_videos=len(raw_videos),
            completed_videos=0,
            status=RoadmapStatus.PROCESSING,
        )
        db.add(roadmap)
        db.flush()  # flush to get roadmap.id without committing yet
        logger.debug("Roadmap row created id=%s", roadmap.id)

        # Step 5 — Bulk insert video records
        video_objects = [
            Video(
                roadmap_id=roadmap.id,
                youtube_id=v["youtube_id"],
                title=v["title"],
                description=v.get("description"),
                thumbnail_url=v.get("thumbnail_url"),
                duration_seconds=v.get("duration_seconds"),
                position=v["position"],
                ai_notes_status=AINotesStatus.PENDING,
            )
            for v in raw_videos
        ]
        db.bulk_save_objects(video_objects)

        # Step 6 — Mark roadmap as ACTIVE
        roadmap.status = RoadmapStatus.ACTIVE
        db.commit()
        db.refresh(roadmap)
        logger.info("Import complete for roadmap_id=%s", roadmap.id)

        # Step 7 — Return response
        return RoadmapImportResponse(
            roadmap_id=roadmap.id,
            title=roadmap.title,
            total_videos=roadmap.total_videos,
            status=roadmap.status,
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

"""
SkillMap AI — Search Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Coordinates text chunk indexing, batch embeddings generation,
vector database storage, similarity matching, and search ranking.
"""

import json
import logging
import uuid
import re
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.roadmap import Roadmap
from app.models.video import Video
from app.models.module import Module
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService
from app.utils.exceptions import ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)


class SearchService:
    """
    Coordinates semantic search:
      - Builds rich text knowledge documents.
      - Indexes video resources on import, notes, or module changes.
      - Executes user search queries against ChromaDB with authorization checks.
    """

    def __init__(self, embedding_service: EmbeddingService | None = None, vector_service: VectorService | None = None):
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_service = vector_service or VectorService()

    def build_knowledge_document(
        self,
        roadmap_title: str,
        module_name: str | None,
        video_title: str,
        video_description: str | None,
        ai_notes_json: str | None
    ) -> str:
        """Combine all textual contexts of a video into a single indexable document block."""
        summary = ""
        key_concepts = []
        important_terms = []
        interview_questions = []

        if ai_notes_json:
            try:
                notes = json.loads(ai_notes_json)
                summary = notes.get("summary", "")
                key_concepts = notes.get("key_concepts", [])
                important_terms = notes.get("important_terms", [])
                interview_questions = notes.get("interview_questions", [])
            except Exception as exc:
                logger.warning("build_knowledge_document: failed to parse ai_notes JSON: %s", exc)
                # Fallback in case it's stored as plain text
                summary = ai_notes_json

        # Format lists helper
        def format_list(items) -> str:
            if isinstance(items, list):
                return ", ".join([str(item) for item in items if item])
            return str(items) if items else ""

        # Construct segments
        parts = [
            f"Roadmap Title: {roadmap_title}",
            f"Module Name: {module_name or 'N/A'}",
            f"Video Title: {video_title}",
            f"Video Description: {video_description or ''}",
            f"AI Summary: {summary}",
            f"Key Concepts: {format_list(key_concepts)}",
            f"Important Terms: {format_list(important_terms)}",
            f"Interview Questions: {format_list(interview_questions)}"
        ]

        # Join non-empty metadata fields
        return "\n\n".join([p for p in parts if p.split(":", 1)[1].strip()])

    def index_video(self, video_id: uuid.UUID, db: Session):
        """Build and index a single video document in ChromaDB."""
        try:
            logger.info("Indexing video %s in ChromaDB", video_id)
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                logger.warning("index_video: Video %s not found in DB", video_id)
                return

            roadmap = db.query(Roadmap).filter(Roadmap.id == video.roadmap_id).first()
            if not roadmap:
                logger.warning("index_video: Roadmap %s not found for video", video.roadmap_id)
                return

            # Resolve module mapping (first assigned module, best effort)
            module_name = None
            module_id = None
            for mv in video.module_videos:
                module_name = mv.module.name
                module_id = mv.module.id
                break

            doc_text = self.build_knowledge_document(
                roadmap_title=roadmap.title,
                module_name=module_name,
                video_title=video.title,
                video_description=video.description,
                ai_notes_json=video.ai_notes
            )

            # Generate local embedding
            embedding = self.embedding_service.generate_embedding(doc_text)

            # Persist to ChromaDB
            self.vector_service.upsert_document(
                document_id=str(video.id),
                roadmap_id=str(roadmap.id),
                video_id=str(video.id),
                module_id=str(module_id) if module_id else None,
                content=doc_text,
                embedding=embedding
            )
            logger.info("index_video: Video %s indexed successfully", video_id)
        except Exception as exc:
            logger.error("index_video: Failed to index video %s: %s", video_id, exc)

    def index_roadmap(self, roadmap_id: uuid.UUID, db: Session):
        """Index all videos of a roadmap using high-performance batch embedding generation."""
        try:
            logger.info("Indexing roadmap %s in ChromaDB", roadmap_id)
            roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
            if not roadmap:
                logger.warning("index_roadmap: Roadmap %s not found in DB", roadmap_id)
                return

            videos = db.query(Video).filter(Video.roadmap_id == roadmap_id).all()
            if not videos:
                logger.info("index_roadmap: No videos to index for roadmap %s", roadmap_id)
                return

            # Resolve module mappings
            modules = db.query(Module).filter(Module.roadmap_id == roadmap_id).all()
            video_to_module = {}
            for mod in modules:
                for mv in mod.module_videos:
                    video_to_module[mv.video_id] = (mod.id, mod.name)

            texts_to_embed = []
            temp_items = []

            for video in videos:
                mod_info = video_to_module.get(video.id, (None, None))
                mod_id, mod_name = mod_info

                doc_text = self.build_knowledge_document(
                    roadmap_title=roadmap.title,
                    module_name=mod_name,
                    video_title=video.title,
                    video_description=video.description,
                    ai_notes_json=video.ai_notes
                )

                texts_to_embed.append(doc_text)
                temp_items.append({
                    "id": str(video.id),
                    "video_id": str(video.id),
                    "roadmap_id": str(roadmap_id),
                    "module_id": str(mod_id) if mod_id else "",
                    "content": doc_text
                })

            if not texts_to_embed:
                return

            # Batch encode
            embeddings = self.embedding_service.generate_embeddings(texts_to_embed)

            # Prep lists for bulk upsert
            ids = [item["id"] for item in temp_items]
            documents = [item["content"] for item in temp_items]
            metadatas = [{
                "roadmap_id": item["roadmap_id"],
                "video_id": item["video_id"],
                "module_id": item["module_id"]
            } for item in temp_items]

            self.vector_service.upsert_documents(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info("index_roadmap: Indexed %d videos for roadmap %s", len(ids), roadmap_id)
        except Exception as exc:
            logger.error("index_roadmap: Failed to index roadmap %s: %s", roadmap_id, exc)

    def search(
        self,
        roadmap_id: uuid.UUID,
        query: str,
        user_id: uuid.UUID,
        db: Session,
        limit: int = 5,
        similarity_threshold: float = 0.30
    ) -> list[dict]:
        """
        Search concepts across an imported roadmap.
        Validates ownership, queries ChromaDB, maps database items,
        ranks, thresholds, and returns structured matches.
        """
        # 1. Authorization check
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            raise NotFoundException("Roadmap")

        if roadmap.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this roadmap.")

        if not query or not query.strip():
            return []

        # 2. Query embedding generation
        query_embedding = self.embedding_service.generate_embedding(query)

        # 3. Search ChromaDB (pull double limit to support deduplication/threshold filters)
        try:
            raw_results = self.vector_service.similarity_search(
                query_embedding=query_embedding,
                roadmap_id=str(roadmap_id),
                limit=limit * 2
            )
        except Exception as exc:
            logger.error("search: ChromaDB similarity query failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Search database is currently offline."
            )

        # Check results
        if not raw_results or not raw_results.get("ids") or len(raw_results["ids"][0]) == 0:
            logger.info("search: No vector hits returned for query %r", query)
            return []

        ids = raw_results["ids"][0]
        distances = raw_results["distances"][0]
        documents = raw_results["documents"][0]
        metadatas = raw_results["metadatas"][0]

        # 4. Hydrate matched documents with database items (title, module details)
        video_ids = [uuid.UUID(m["video_id"]) for m in metadatas if m.get("video_id")]
        videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
        video_map = {v.id: v for v in videos}

        # Resolve module names
        modules = db.query(Module).filter(Module.roadmap_id == roadmap_id).all()
        video_to_module_name = {}
        for mod in modules:
            for mv in mod.module_videos:
                video_to_module_name[mv.video_id] = mod.name

        results = []
        for idx, doc_id in enumerate(ids):
            meta = metadatas[idx]
            dist = distances[idx]
            content = documents[idx]

            vid_id_str = meta.get("video_id")
            if not vid_id_str:
                continue

            vid_id = uuid.UUID(vid_id_str)
            video_obj = video_map.get(vid_id)
            if not video_obj:
                continue

            # Cosine similarity score = 1.0 - cosine distance (clamped)
            similarity = max(0.0, min(1.0, 1.0 - dist))

            # Filter below threshold
            if similarity < similarity_threshold:
                continue

            module_name = video_to_module_name.get(vid_id)
            preview = self._get_content_preview(content, query)

            results.append({
                "video_id": vid_id,
                "video_title": video_obj.title,
                "module_name": module_name,
                "similarity_score": round(similarity, 2),
                "matched_content_preview": preview
            })

        # Rank results
        results.sort(key=lambda x: x["similarity_score"], reverse=True)

        # Deduplicate
        seen_videos = set()
        deduped = []
        for r in results:
            if r["video_id"] not in seen_videos:
                seen_videos.add(r["video_id"])
                deduped.append(r)

        logger.info("search: Found %d hits after thresholding and deduplication.", len(deduped[:limit]))
        return deduped[:limit]

    def _get_content_preview(self, content: str, query: str, length: int = 160) -> str:
        """Extract a snippet of the document around the matched terms."""
        content_clean = " ".join(content.split())
        
        # Split query into words to look for matches
        words = [w for w in re.split(r'\W+', query.lower()) if len(w) > 3]
        best_idx = -1
        for word in words:
            idx = content_clean.lower().find(word)
            if idx != -1:
                best_idx = idx
                break

        if best_idx != -1:
            start = max(0, best_idx - 40)
            end = min(len(content_clean), start + length)
            
            # Align window starts nicely at spaces
            if start > 0:
                space_idx = content_clean.find(" ", start)
                if space_idx != -1 and space_idx < best_idx:
                    start = space_idx + 1
            preview = content_clean[start:end]
            
            if start > 0:
                preview = "..." + preview
            if end < len(content_clean):
                preview = preview + "..."
            return preview
        else:
            # Fallback to the first part of the document
            if len(content_clean) <= length:
                return content_clean
            return content_clean[:length] + "..."

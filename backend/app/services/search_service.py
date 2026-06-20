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


def clean_text_for_embedding(text: str | None) -> str:
    """
    Cleans embedding documents by ignoring and removing:
    - URLs (http/https and www links)
    - Email addresses
    - Timestamp dumps (e.g. 12:34 or 1:23:45)
    - Markdown links [text](url) -> text
    - Lines or segments containing promotional/social keywords (Discord, GitHub, Twitter, sponsors, ads, etc.)
    """
    if not text:
        return ""
    
    # Remove markdown link syntax first: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\((https?://\S+|www\.\S+)\)', r'\1', text)
    # Remove raw URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    # Remove emails
    text = re.sub(r'\S+@\S+', '', text)
    # Remove timestamp dumps like [01:23:45] or 04:30
    text = re.sub(r'\[?\b\d{1,2}:\d{2}(?::\d{2})?\b\]?', '', text)
    
    # Split into lines/segments to filter out promotional content
    segments = re.split(r'(\n|\. |\! |\? )', text)
    cleaned_segments = []
    
    promo_keywords = {
        "discord", "github", "twitter", "instagram", "facebook", "patreon", 
        "paypal", "sponsor", "coupon", "discount", "promo", "subscribe", 
        "follow me", "merch", "website", "shop", "advertisement", "advertise",
        "ad-free", "social media"
    }
    
    for seg in segments:
        if any(kw in seg.lower() for kw in promo_keywords):
            continue
        cleaned_segments.append(seg)
        
    cleaned_text = "".join(cleaned_segments)
    # Normalize spaces
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return cleaned_text


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
        module_description: str | None,
        video_title: str,
        ai_notes_json: str | None
    ) -> str:
        """Combine all cleaned textual contexts of a video module into a single indexable document block."""
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

        # Clean all individual textual fields
        roadmap_title_clean = clean_text_for_embedding(roadmap_title)
        module_name_clean = clean_text_for_embedding(module_name)
        module_description_clean = clean_text_for_embedding(module_description)
        video_title_clean = clean_text_for_embedding(video_title)
        summary_clean = clean_text_for_embedding(summary)
        
        cleaned_concepts = [clean_text_for_embedding(c) for c in key_concepts if c]
        cleaned_terms = [clean_text_for_embedding(t) for t in important_terms if t]
        cleaned_questions = [clean_text_for_embedding(q) for q in interview_questions if q]

        # Construct segments
        parts = [
            f"Roadmap Title: {roadmap_title_clean}",
            f"Module Name: {module_name_clean or 'N/A'}",
            f"Module Overview: {module_description_clean or ''}",
            f"Video Title: {video_title_clean}",
            f"AI Summary: {summary_clean}",
            f"Key Concepts: {format_list(cleaned_concepts)}",
            f"Important Terms: {format_list(cleaned_terms)}",
            f"Interview Questions: {format_list(cleaned_questions)}"
        ]

        # Join non-empty metadata fields
        return "\n\n".join([p for p in parts if p.split(":", 1)[1].strip()])

    def chunk_transcript(self, text: str) -> list[str]:
        """
        Chunks transcript text into cohesive blocks of 500-1000 words.
        Ensures chunks align on sentence boundaries where possible.
        """
        if not text:
            return []
        words = text.split()
        chunks = []
        target_size = 750
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= 500:
                if len(current_chunk) >= target_size or word.endswith('.') or word.endswith('?') or word.endswith('!'):
                    if len(current_chunk) <= 1000:
                        chunks.append(" ".join(current_chunk))
                        current_chunk = []
            if len(current_chunk) >= 1000:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    def chunk_transcript_with_timestamps(self, transcript_json: str) -> list[dict]:
        """
        Chunks transcript text into cohesive blocks of 500-1000 words.
        Expects a JSON string representing a list of dicts with 'text' and 'start'.
        Returns a list of dicts: {'text': str, 'start_time': float}
        """
        try:
            entries = json.loads(transcript_json)
            if not isinstance(entries, list):
                return []
        except Exception as exc:
            logger.warning("chunk_transcript_with_timestamps: invalid JSON: %s", exc)
            return []

        chunks = []
        target_size = 750
        current_chunk_entries = []
        current_chunk_words = 0

        for entry in entries:
            text = entry.get("text", "")
            words = text.split()
            if not words:
                continue
            
            if current_chunk_words + len(words) > 1000 and current_chunk_entries:
                chunk_text = " ".join([e.get("text", "") for e in current_chunk_entries])
                start_time = current_chunk_entries[0].get("start", 0.0)
                chunks.append({
                    "text": chunk_text,
                    "start_time": start_time
                })
                current_chunk_entries = []
                current_chunk_words = 0

            current_chunk_entries.append(entry)
            current_chunk_words += len(words)

            if current_chunk_words >= 500:
                last_word = words[-1]
                if current_chunk_words >= target_size or last_word.endswith('.') or last_word.endswith('?') or last_word.endswith('!'):
                    chunk_text = " ".join([e.get("text", "") for e in current_chunk_entries])
                    start_time = current_chunk_entries[0].get("start", 0.0)
                    chunks.append({
                        "text": chunk_text,
                        "start_time": start_time
                    })
                    current_chunk_entries = []
                    current_chunk_words = 0

        if current_chunk_entries:
            chunk_text = " ".join([e.get("text", "") for e in current_chunk_entries])
            start_time = current_chunk_entries[0].get("start", 0.0)
            chunks.append({
                "text": chunk_text,
                "start_time": start_time
            })

        return chunks

    def index_video(self, video_id: uuid.UUID, db: Session):
        """Build and index a single video document and its transcript chunks in ChromaDB."""
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
            module_description = None
            module_id = None
            for mv in video.module_videos:
                module_name = mv.module.name
                module_description = mv.module.description
                module_id = mv.module.id
                break

            # 1. Clear any existing documents for this video in ChromaDB
            self.vector_service.collection.delete(where={"video_id": str(video.id)})
            logger.info("index_video: Cleared existing documents in ChromaDB for video %s", video.id)

            # 2. Build and index the metadata/notes knowledge document
            doc_text = self.build_knowledge_document(
                roadmap_title=roadmap.title,
                module_name=module_name,
                module_description=module_description,
                video_title=video.title,
                ai_notes_json=video.ai_notes
            )

            embedding = self.embedding_service.generate_embedding(doc_text)
            source_type = "notes" if video.ai_notes else "metadata"

            self.vector_service.collection.upsert(
                ids=[str(video.id)],
                embeddings=[embedding],
                documents=[doc_text],
                metadatas=[{
                    "roadmap_id": str(roadmap.id),
                    "video_id": str(video.id),
                    "module_id": str(module_id) if module_id else "",
                    "source_type": source_type
                }]
            )
            logger.info("index_video: Video %s metadata/notes indexed successfully (source_type=%s)", video_id, source_type)

            # 3. Chunk and index the transcript if available
            if video.transcript_text:
                is_json = False
                try:
                    parsed = json.loads(video.transcript_text)
                    if isinstance(parsed, list):
                        is_json = True
                except Exception:
                    pass

                if is_json:
                    chunks = self.chunk_transcript_with_timestamps(video.transcript_text)
                    if chunks:
                        logger.info("index_video: Indexing %d timestamped transcript chunks for video %s", len(chunks), video_id)
                        chunk_texts = []
                        chunk_ids = []
                        chunk_metadatas = []
                        
                        for idx, chunk in enumerate(chunks):
                            chunk_ids.append(f"{video.id}_chunk_{idx}")
                            cleaned_chunk_text = clean_text_for_embedding(chunk["text"])
                            chunk_texts.append(cleaned_chunk_text)
                            chunk_metadatas.append({
                                "roadmap_id": str(roadmap.id),
                                "video_id": str(video.id),
                                "module_id": str(module_id) if module_id else "",
                                "chunk_index": idx,
                                "start_time": chunk["start_time"],
                                "source_type": "transcript"
                            })
                        
                        chunk_embeddings = self.embedding_service.generate_embeddings(chunk_texts)
                        self.vector_service.collection.upsert(
                            ids=chunk_ids,
                            embeddings=chunk_embeddings,
                            documents=chunk_texts,
                            metadatas=chunk_metadatas
                        )
                        logger.info("index_video: %d timestamped transcript chunks indexed successfully for video %s", len(chunks), video_id)
                else:
                    chunks = self.chunk_transcript(video.transcript_text)
                    if chunks:
                        logger.info("index_video: Indexing %d transcript chunks for video %s", len(chunks), video_id)
                        chunk_texts = []
                        chunk_ids = []
                        chunk_metadatas = []
                        
                        for idx, chunk in enumerate(chunks):
                            chunk_ids.append(f"{video.id}_chunk_{idx}")
                            cleaned_chunk_text = clean_text_for_embedding(chunk)
                            chunk_texts.append(cleaned_chunk_text)
                            chunk_metadatas.append({
                                "roadmap_id": str(roadmap.id),
                                "video_id": str(video.id),
                                "module_id": str(module_id) if module_id else "",
                                "chunk_index": idx,
                                "source_type": "transcript"
                            })
                        
                        chunk_embeddings = self.embedding_service.generate_embeddings(chunk_texts)
                        self.vector_service.collection.upsert(
                            ids=chunk_ids,
                            embeddings=chunk_embeddings,
                            documents=chunk_texts,
                            metadatas=chunk_metadatas
                        )
                        logger.info("index_video: %d transcript chunks indexed successfully for video %s", len(chunks), video_id)

        except Exception as exc:
            logger.error("index_video: Failed to index video %s: %s", video_id, exc)

    def index_roadmap(self, roadmap_id: uuid.UUID, db: Session):
        """Index all videos and transcript chunks of a roadmap using high-performance batch embedding generation."""
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
                    video_to_module[mv.video_id] = (mod.id, mod.name, mod.description)

            # 1. Clear any existing documents for this roadmap in ChromaDB
            self.vector_service.delete_by_roadmap(str(roadmap_id))
            logger.info("index_roadmap: Cleared existing documents in ChromaDB for roadmap %s", roadmap_id)

            texts_to_embed = []
            temp_items = []

            for video in videos:
                mod_info = video_to_module.get(video.id, (None, None, None))
                mod_id, mod_name, mod_description = mod_info

                # Metadata/notes document
                doc_text = self.build_knowledge_document(
                    roadmap_title=roadmap.title,
                    module_name=mod_name,
                    module_description=mod_description,
                    video_title=video.title,
                    ai_notes_json=video.ai_notes
                )

                source_type = "notes" if video.ai_notes else "metadata"

                texts_to_embed.append(doc_text)
                temp_items.append({
                    "id": str(video.id),
                    "video_id": str(video.id),
                    "roadmap_id": str(roadmap_id),
                    "module_id": str(mod_id) if mod_id else "",
                    "source_type": source_type,
                    "content": doc_text
                })

                # Transcript chunks
                if video.transcript_text:
                    is_json = False
                    try:
                        parsed = json.loads(video.transcript_text)
                        if isinstance(parsed, list):
                            is_json = True
                    except Exception:
                        pass

                    if is_json:
                        chunks = self.chunk_transcript_with_timestamps(video.transcript_text)
                        for idx, chunk in enumerate(chunks):
                            # For single video segments, check if we can resolve specific module mapping
                            # based on the chunk's start time
                            chunk_mod_id = mod_id
                            if roadmap.playlist_url and ("/watch?v=" in roadmap.playlist_url or "youtu.be/" in roadmap.playlist_url):
                                # It's a single video, let's find the module that covers this timestamp
                                chunk_start = chunk["start_time"]
                                best_mod_id = mod_id
                                best_start = -1
                                for m in modules:
                                    if m.module_start_time is not None and m.module_start_time <= chunk_start:
                                        if m.module_start_time > best_start:
                                            best_start = m.module_start_time
                                            best_mod_id = m.id
                                chunk_mod_id = best_mod_id

                            cleaned_chunk_text = clean_text_for_embedding(chunk["text"])
                            texts_to_embed.append(cleaned_chunk_text)
                            temp_items.append({
                                "id": f"{video.id}_chunk_{idx}",
                                "video_id": str(video.id),
                                "roadmap_id": str(roadmap_id),
                                "module_id": str(chunk_mod_id) if chunk_mod_id else "",
                                "chunk_index": idx,
                                "start_time": chunk["start_time"],
                                "source_type": "transcript",
                                "content": cleaned_chunk_text
                            })
                    else:
                        chunks = self.chunk_transcript(video.transcript_text)
                        for idx, chunk in enumerate(chunks):
                            cleaned_chunk_text = clean_text_for_embedding(chunk)
                            texts_to_embed.append(cleaned_chunk_text)
                            temp_items.append({
                                "id": f"{video.id}_chunk_{idx}",
                                "video_id": str(video.id),
                                "roadmap_id": str(roadmap_id),
                                "module_id": str(mod_id) if mod_id else "",
                                "chunk_index": idx,
                                "source_type": "transcript",
                                "content": cleaned_chunk_text
                            })

            if not texts_to_embed:
                return

            # Batch encode
            embeddings = self.embedding_service.generate_embeddings(texts_to_embed)

            # Prep lists for bulk upsert
            ids = [item["id"] for item in temp_items]
            documents = [item["content"] for item in temp_items]
            metadatas = []
            for item in temp_items:
                meta = {
                    "roadmap_id": item["roadmap_id"],
                    "video_id": item["video_id"],
                    "module_id": item["module_id"],
                    "source_type": item["source_type"]
                }
                if "chunk_index" in item:
                    meta["chunk_index"] = item["chunk_index"]
                if "start_time" in item:
                    meta["start_time"] = item["start_time"]
                metadatas.append(meta)

            self.vector_service.upsert_documents(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info("index_roadmap: Indexed %d items (videos + chunks) for roadmap %s", len(ids), roadmap_id)
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

        # 3. Search ChromaDB (pull higher limit to support deduplication/threshold filters)
        try:
            raw_results = self.vector_service.similarity_search(
                query_embedding=query_embedding,
                roadmap_id=str(roadmap_id),
                limit=limit * 4
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

            # Determine source type
            source_type = meta.get("source_type", "metadata")
            if source_type == "transcript":
                pass
            elif source_type in ("metadata", "notes"):
                # Dynamically classify notes/metadata
                if "AI Summary:" in content:
                    parts = content.split("AI Summary:", 1)
                    notes_part = "AI Summary:" + parts[1]
                    
                    # Split query into words to look for matches
                    words = [w for w in re.split(r'\W+', query.lower()) if len(w) > 3]
                    matched_in_notes = False
                    for word in words:
                        if word in notes_part.lower():
                            matched_in_notes = True
                            break
                    if matched_in_notes:
                        source_type = "notes"
                    else:
                        source_type = "metadata"
                else:
                    source_type = "metadata"
            else:
                source_type = "metadata"

            module_name = video_to_module_name.get(vid_id)
            preview = self._get_content_preview(content, query)

            results.append({
                "video_id": vid_id,
                "video_title": video_obj.title,
                "module_name": module_name,
                "similarity_score": round(similarity, 2),
                "matched_content_preview": preview,
                "matched_snippet": preview,
                "source_type": source_type,
                "start_time": meta.get("start_time")
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
            if len(content_clean) <= length:
                return content_clean
            return content_clean[:length] + "..."

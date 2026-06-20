"""
SkillMap AI — Vector Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with a local persistent ChromaDB collection for semantic vector retrieval.
"""

import os
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


class VectorService:
    """
    Handles connection and queries to the ChromaDB vector database.
    Documents are stored with metadata to support roadmap-isolated filtering.
    """

    def __init__(self):
        settings = get_settings()
        
        # Determine the database path (relative to the backend/ directory)
        db_path = getattr(settings, "chroma_db_dir", "chroma_db")
        if not os.path.isabs(db_path):
            # Resolve relative to the current working directory
            db_path = os.path.abspath(db_path)
            
        logger.info("Initializing ChromaDB PersistentClient at: %s", db_path)
        
        import chromadb
        # Initialize client and collection
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Create or fetch collection using Cosine distance space
        self.collection = self.client.get_or_create_collection(
            name="roadmap_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("ChromaDB collection 'roadmap_knowledge' loaded successfully.")

    def upsert_document(
        self,
        document_id: str,
        roadmap_id: str,
        video_id: str,
        module_id: str | None,
        content: str,
        embedding: list[float]
    ):
        """Insert or update a single document with its embedding and metadata."""
        metadata = {
            "roadmap_id": roadmap_id,
            "video_id": video_id,
            "module_id": module_id or "",
        }
        logger.info("ChromaDB: Upserting document ID %s for roadmap %s", document_id, roadmap_id)
        self.collection.upsert(
            ids=[document_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )

    def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict]
    ):
        """Batch insert or update documents for optimized index loading."""
        if not ids:
            return
            
        logger.info("ChromaDB: Bulk upserting %d documents", len(ids))
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def delete_document(self, document_id: str):
        """Delete a document by its document ID."""
        logger.info("ChromaDB: Deleting document ID %s", document_id)
        try:
            self.collection.delete(ids=[document_id])
        except Exception as exc:
            logger.warning("ChromaDB deletion failed for %s: %s", document_id, exc)

    def delete_by_roadmap(self, roadmap_id: str):
        """Delete all documents associated with a specific roadmap."""
        logger.info("ChromaDB: Deleting all documents for roadmap %s", roadmap_id)
        try:
            self.collection.delete(where={"roadmap_id": roadmap_id})
        except Exception as exc:
            logger.warning("ChromaDB deletion failed for roadmap %s: %s", roadmap_id, exc)

    def similarity_search(
        self,
        query_embedding: list[float],
        roadmap_id: str,
        limit: int = 5
    ) -> dict:
        """
        Query ChromaDB for the closest matches using cosine similarity,
        isolated to the specified roadmap.
        """
        logger.info("ChromaDB: Querying nearest neighbors for roadmap %s (limit: %d)", roadmap_id, limit)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"roadmap_id": roadmap_id}
        )
        return results

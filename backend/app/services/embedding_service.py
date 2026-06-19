"""
SkillMap AI — Embedding Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Exposes functions to generate text embeddings locally using sentence-transformers.
"""

import logging
from functools import lru_cache
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service to generate embeddings using the sentence-transformers model.
    Loads the model once on-demand and caches results for single texts.
    """

    _model = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """Lazy-load the model once per process lifetime."""
        if cls._model is None:
            logger.info("Initializing local SentenceTransformer ('all-MiniLM-L6-v2')...")
            # Load model (will download to local cache if not present)
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded successfully.")
        return cls._model

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text. Uses caching internally.
        
        Returns:
            A list of 384 floats representing the vector.
        """
        if not text or not text.strip():
            # Return a zero vector of dimension 384 for empty text
            return [0.0] * 384
            
        logger.info("Embedding generated for text (length: %d chars)", len(text))
        return self._cached_encode(text)

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts in batch. High throughput.
        
        Returns:
            A list of list of floats.
        """
        if not texts:
            return []
            
        logger.info("Generating batch embeddings for %d texts...", len(texts))
        model = self.get_model()
        cleaned_texts = [t if t and t.strip() else " " for t in texts]
        embeddings = model.encode(cleaned_texts, batch_size=32, show_progress_bar=False)
        logger.info("Batch embeddings generated successfully.")
        return embeddings.tolist()

    @lru_cache(maxsize=1024)
    def _cached_encode(self, text: str) -> list[float]:
        """Cached single text encoding to avoid redundant inferences."""
        model = self.get_model()
        embedding = model.encode(text, show_progress_bar=False)
        return embedding.tolist()

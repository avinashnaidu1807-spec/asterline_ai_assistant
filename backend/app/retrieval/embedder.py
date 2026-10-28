"""Local embedding provider using ONNX Runtime for all-MiniLM-L6-v2."""
from __future__ import annotations

import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger(__name__)

_embedder_instance = None


class LocalEmbedder:
    """Computes local embeddings without requiring torch or external APIs."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._fn = None
        self._init_backend()

    def _init_backend(self):
        try:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
            self._fn = ONNXMiniLM_L6_V2()
            logger.info("Local ONNX MiniLM-L6-v2 embedding function initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize ONNXMiniLM_L6_V2: {e}. Trying sentence_transformers...")
            try:
                from sentence_transformers import SentenceTransformer
                self._fn = SentenceTransformer(self.model_name)
                logger.info(f"SentenceTransformer {self.model_name} initialized successfully.")
            except Exception as e2:
                logger.error(f"Failed to initialize any local embedding engine: {e2}")
                raise

    def encode(self, texts: Union[str, List[str]], show_progress_bar: bool = False) -> np.ndarray:
        if isinstance(texts, str):
            texts = [texts]
        if hasattr(self._fn, "encode"):
            res = self._fn.encode(texts, show_progress_bar=show_progress_bar)
            return np.array(res)
        else:
            # Chroma ONNX embedding function takes a list of strings and returns embeddings
            res = self._fn(texts)
            return np.array(res)


def get_local_embedder() -> LocalEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = LocalEmbedder()
    return _embedder_instance


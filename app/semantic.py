from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class SemanticBackend:
    model_path: str
    batch_size: int = 32
    _model: "SentenceTransformer" | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(self.model_path)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        vectors = self._model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)



def load_semantic_backend(model_path: str, batch_size: int = 32) -> SemanticBackend | None:
    model_path = (model_path or "").strip()
    if not model_path:
        return None
        
    # Truyền thẳng model_path, bỏ qua việc ép kiểu qua thư viện Path
    return SemanticBackend(model_path=model_path, batch_size=batch_size)

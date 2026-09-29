from app.embedding import VietnameseEmbedder
from app.vector_store import VectorStore


class SemanticIndexer:

    def __init__(self):
        self.embedder = VietnameseEmbedder()
        self.store: VectorStore | None = None

    # ------------------------------------------------------------------
    # Xây index từ danh sách văn bản
    # ------------------------------------------------------------------

    def build(self, documents: list[str]) -> None:

        if not documents:
            return

        # FIX #1: dùng encode() thay vì embed() (không tồn tại)
        all_vectors = self.embedder.encode(documents)   # shape (N, dim)
        dim = all_vectors.shape[1]

        self.store = VectorStore(dim)
        self.store.add(all_vectors, documents)

    # ------------------------------------------------------------------
    # Truy vấn tương đồng
    # ------------------------------------------------------------------

    def query(self, text: str, top_k: int = 5) -> list[str]:

        # FIX #2: guard kiểm tra store trước khi dùng
        if self.store is None:
            return []

        # FIX #1: dùng encode() — trả về array (1, dim)
        vector = self.embedder.encode([text])[0]

        return self.store.search(vector, top_k)

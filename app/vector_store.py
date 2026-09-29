import faiss
import numpy as np

class VectorStore:

    def __init__(self, dim):
        self.index = faiss.IndexFlatL2(dim)
        self.texts = []

    def add(self, vectors, texts):
        self.index.add(np.array(vectors).astype("float32"))
        self.texts.extend(texts)

    def search(self, vector, k=5):
        D, I = self.index.search(np.array([vector]).astype("float32"), k)

        results = []
        for idx in I[0]:
            if idx < len(self.texts):
                results.append(self.texts[idx])

        return results
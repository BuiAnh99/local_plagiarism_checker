from sentence_transformers import SentenceTransformer

class VietnameseEmbedder:

    def __init__(self):

        self.model = SentenceTransformer(
            "keepitreal/vietnamese-sbert"
        )

    def encode(self, texts):

        return self.model.encode(texts)
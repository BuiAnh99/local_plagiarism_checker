import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def build_similarity_matrix(embeddings):

    matrix = cosine_similarity(embeddings)

    return matrix
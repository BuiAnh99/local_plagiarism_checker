def shingles(text, k=5):

    words = text.split()

    if not words:
        return set()

    if len(words) <= k:
        return {" ".join(words)}

    return set(
        " ".join(words[i:i+k])
        for i in range(len(words)-k+1)
    )


def jaccard_similarity(a, b):

    inter = len(a & b)
    union = len(a | b)

    if union == 0:
        return 0

    return inter / union

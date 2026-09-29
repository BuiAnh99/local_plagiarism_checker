from difflib import SequenceMatcher

def highlight_similarity(a, b):

    matcher = SequenceMatcher(None, a, b)

    blocks = matcher.get_matching_blocks()

    matches = []

    for block in blocks:

        if block.size > 20:
            matches.append({
                "text": a[block.a:block.a+block.size],
                "pos_a": block.a,
                "pos_b": block.b,
                "length": block.size
            })

    return matches
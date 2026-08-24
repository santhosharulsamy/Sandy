"""Tiny 'did you mean?' helper for friendly error messages.

Uses Levenshtein edit distance to find the closest known name to one the
user typed. Kept dependency-free and small.
"""


def _edit_distance(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(
                prev[j] + 1,        # deletion
                cur[j - 1] + 1,     # insertion
                prev[j - 1] + cost,  # substitution
            ))
        prev = cur
    return prev[-1]


def closest_name(name, candidates):
    """Return the closest candidate to `name`, or None if none is close
    enough to be a plausible typo."""
    best = None
    best_dist = None
    for cand in candidates:
        d = _edit_distance(name, cand)
        if best_dist is None or d < best_dist:
            best_dist = d
            best = cand
    if best is None:
        return None
    # Only suggest when it's plausibly a typo, not a wild guess.
    threshold = max(2, len(name) // 2)
    if best_dist <= threshold:
        return best
    return None

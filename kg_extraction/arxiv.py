# read the arxiv json file line by line (too big to load at once)

import json
import random

# foreach paper, get a dict with metadata.
#  Skip papers that don't match
def iter_papers(path, categories, search, limit, skip_ids):
    # limit=0 means no limit, skip_ids = papers we already did
    found = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if limit and found >= limit:
                return
            try:
                paper = json.loads(line)
            except json.JSONDecodeError:
                continue
            if paper.get("id") in skip_ids:
                continue
            if not paper.get("abstract"):
                continue
            if categories:
                cats = paper.get("categories", "").split()
                if not any(c.startswith(want) for want in categories for c in cats):
                    continue
            if search:
                haystack = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
                if search.lower() not in haystack:
                    continue
            found += 1
            yield paper


# pick n random papers from the matches in one pass (reservoir sampling).
# same seed => same papers, so the dataset is reproducible
def sample_papers(path, categories, search, n, seed):
    rng = random.Random(seed)
    reservoir = []
    seen = 0
    for paper in iter_papers(path, categories, search, 0, set()):
        seen += 1
        if len(reservoir) < n:
            reservoir.append(paper)
        else:
            j = rng.randint(0, seen - 1)  # keep each paper with equal probability
            if j < n:
                reservoir[j] = paper
    return reservoir

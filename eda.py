import json
from collections import Counter
import time

FILE = "arxiv-metadata-oai-snapshot.json"

categories = Counter()
years = Counter()
abstract_lengths = []
title_lengths = []
authors_per_paper = []
versions_per_paper = []
top_authors = Counter()
no_abstract = 0
has_doi = 0

print("Reading dataset...\n")
start = time.time()
i = 0

with open(FILE, "r") as f:
    for line in f:
        try:
            paper = json.loads(line)
        except json.JSONDecodeError:
            continue

        i += 1
        if i % 100_000 == 0:
            print(f"  ... {i:,} papers read ({time.time()-start:.0f}s)")

        # Categories
        for cat in paper.get("categories", "").split():
            categories[cat.split(".")[0]] += 1

        # Year
        update_date = paper.get("update_date", "")
        if update_date:
            years[update_date[:4]] += 1

        # Abstract
        abstract = paper.get("abstract", "")
        if not abstract.strip():
            no_abstract += 1
        else:
            abstract_lengths.append(len(abstract.split()))

        # Title
        title = paper.get("title", "")
        title_lengths.append(len(title.split()))

        # Authors
        authors = paper.get("authors_parsed", [])
        authors_per_paper.append(len(authors))
        for author in authors:
            if author and len(author) >= 2:
                top_authors[f"{author[0]}, {author[1]}"] += 1

        # Versions
        versions_per_paper.append(len(paper.get("versions", [])))

        # DOI
        if paper.get("doi"):
            has_doi += 1

elapsed = time.time() - start
print(f"\nCompleted: {i:,} papers in {elapsed:.1f}s\n")

print("=" * 45)
print("TOP 10 CATEGORIES")
print("=" * 45)
for cat, count in categories.most_common(10):
    print(f"  {cat:<12} {count:>9,} papers")

print()
print("=" * 45)
print("YEAR DISTRIBUTION (last 10)")
print("=" * 45)
for year, count in sorted(years.items())[-10:]:
    bar = "█" * (count // 10_000)
    print(f"  {year}  {count:>8,}  {bar}")

print()
print("=" * 45)
print("ABSTRACT STATISTICS (words)")
print("=" * 45)
print(f"  Average: {sum(abstract_lengths)/len(abstract_lengths):.0f} words")
print(f"  Minimum: {min(abstract_lengths)}")
print(f"  Maximum: {max(abstract_lengths)}")

print()
print("=" * 45)
print("TITLE STATISTICS (words)")
print("=" * 45)
print(f"  Average: {sum(title_lengths)/len(title_lengths):.1f} words")
print(f"  Minimum: {min(title_lengths)}")
print(f"  Maximum: {max(title_lengths)}")

print()
print("=" * 45)
print("AUTHORS PER PAPER")
print("=" * 45)
print(f"  Average: {sum(authors_per_paper)/len(authors_per_paper):.1f} authors")
print(f"  Maximum: {max(authors_per_paper)} authors")
solo = sum(1 for x in authors_per_paper if x == 1)
print(f"  Single-author papers: {solo:,} ({100*solo/i:.1f}%)")

print()
print("=" * 45)
print("VERSIONS PER PAPER")
print("=" * 45)
print(f"  Average versions: {sum(versions_per_paper)/len(versions_per_paper):.1f}")
print(f"  Max versions:     {max(versions_per_paper)}")
v1_only = sum(1 for v in versions_per_paper if v == 1)
print(f"  v1 only:          {v1_only:,} ({100*v1_only/i:.1f}%)")

print()
print("=" * 45)
print("DATA QUALITY")
print("=" * 45)
print(f"  Papers without abstract: {no_abstract:,} ({100*no_abstract/i:.1f}%)")
print(f"  Papers with DOI:         {has_doi:,} ({100*has_doi/i:.1f}%)")

print()
print("=" * 45)
print("TOP 10 MOST PROLIFIC AUTHORS")
print("=" * 45)
for author, count in top_authors.most_common(10):
    print(f"  {author:<35} {count:>4} papers")
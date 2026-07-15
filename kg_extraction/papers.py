# export the paper records as a flat "articles" table (CSV or JSON) -- the RAG
# corpus that pairs with the RDF knowledge graph. Join key: arxiv_id / url,
# which matches each Paper IRI (https://arxiv.org/abs/<id>) in the graph.

import csv
import json
import os

ARXIV_ABS = "https://arxiv.org/abs/"

# column order for CSV / key order for JSON
FIELDS = ["arxiv_id", "url", "title", "authors", "author_keys",
          "categories", "update_date", "doi", "journal_ref", "abstract"]


def _rows(graph):
    for pid, p in graph["papers"].items():
        yield {
            "arxiv_id": pid,
            "url": ARXIV_ABS + pid,
            "title": p.get("title", ""),
            "authors": p.get("authors", ""),
            "author_keys": p.get("author_keys", []),
            "categories": p.get("categories", []),
            "update_date": p.get("update_date", ""),
            "doi": p.get("doi", ""),
            "journal_ref": p.get("journal_ref", ""),
            "abstract": p.get("abstract", ""),
        }


def save_papers(graph, path, fmt="csv"):
    """Write the paper records to `path` as CSV (fmt='csv') or a JSON array.

    Returns the number of rows. Multi-valued fields (author_keys, categories)
    stay as arrays in JSON and are joined with '|' in CSV. tmp file + rename so
    a crash can't leave a half-written file."""
    rows = list(_rows(graph))
    tmp = path + ".tmp"
    if fmt == "json":
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
            f.write("\n")
    else:  # csv -- newline="" is required by the csv module on Windows
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for r in rows:
                out = dict(r)
                out["author_keys"] = "|".join(r["author_keys"])
                out["categories"] = "|".join(r["categories"])
                w.writerow(out)
    os.replace(tmp, path)
    return len(rows)

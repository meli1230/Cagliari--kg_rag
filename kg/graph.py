# in-memory graph model: add papers + their authors and categories.
# serialization lives in rdf.py (Turtle/TriG for GraphDB).

from .utils import author_key, clean_text


def new_graph():
    return {"papers": {}, "authors": {}, "categories": {}}


def ingest_paper(graph, paper):
    # add paper + authors + categories
    pid = paper["id"]
    if pid in graph["papers"]:
        return

    author_keys = []
    display_names = []
    for entry in paper.get("authors_parsed") or []:
        last = entry[0] if len(entry) > 0 else ""
        first = entry[1] if len(entry) > 1 else ""
        suffix = entry[2] if len(entry) > 2 else ""
        display = " ".join(p for p in (first, last, suffix) if p).strip()
        key = author_key(last, first)
        if not display or not key:
            continue
        author = graph["authors"].get(key)
        if author is None:
            graph["authors"][key] = {"name": display, "paper_count": 1}
        else:
            author["paper_count"] += 1
        author_keys.append(key)
        display_names.append(display)

    cats = paper.get("categories", "").split()
    for c in cats:
        graph["categories"][c] = graph["categories"].get(c, 0) + 1

    graph["papers"][pid] = {
        "title": clean_text(paper.get("title")),
        "abstract": clean_text(paper.get("abstract")),
        "authors": ", ".join(display_names) or clean_text(paper.get("authors")),
        "author_keys": author_keys,
        "categories": cats,
        "doi": paper.get("doi") or "",
        "journal_ref": paper.get("journal-ref") or "",
        "update_date": paper.get("update_date") or "",
    }


def graph_stats(graph):
    # counts for the run summary (relationships = authorship + category edges)
    rels = sum(len(p["author_keys"]) + len(p["categories"])
               for p in graph["papers"].values())
    return {
        "papers": len(graph["papers"]),
        "authors": len(graph["authors"]),
        "categories": len(graph["categories"]),
        "nodes": len(graph["papers"]) + len(graph["authors"]) + len(graph["categories"]),
        "relationships": rels,
    }

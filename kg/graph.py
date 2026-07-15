# add papers, save/load jsonl

import json
import os
import time

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


def build_export(graph):
    # turn the dicts into nodes + relationships lists
    nodes = []
    relationships = []

    for pid, p in graph["papers"].items():
        nodes.append({
            "id": f"paper:{pid}",
            "labels": ["Paper"],
            "properties": {
                "arxiv_id": pid,
                "title": p["title"],
                "abstract": p["abstract"],
                "authors": p["authors"],
                "author_keys": p["author_keys"],
                "categories": p["categories"],
                "doi": p["doi"],
                "journal_ref": p["journal_ref"],
                "update_date": p["update_date"],
            },
        })
        for i, ak in enumerate(p["author_keys"], 1):
            relationships.append({
                "source": f"author:{ak}", "target": f"paper:{pid}",
                "type": "AUTHORED", "properties": {"position": i},
            })
        for c in p["categories"]:
            relationships.append({
                "source": f"paper:{pid}", "target": f"category:{c}",
                "type": "IN_CATEGORY", "properties": {},
            })

    for key, a in graph["authors"].items():
        nodes.append({
            "id": f"author:{key}", "labels": ["Author"],
            "properties": {"name": a["name"], "paper_count": a["paper_count"]},
        })

    for name, count in graph["categories"].items():
        nodes.append({
            "id": f"category:{name}", "labels": ["Category"],
            "properties": {"name": name, "paper_count": count},
        })

    return nodes, relationships


def save_graph(graph, path):
    # jsonl: one object per line -> stats line, then a line per node, then per relationship.
    # write to a tmp file then rename so a crash can't leave a half file
    nodes, relationships = build_export(graph)
    stats = {
        "papers": len(graph["papers"]),
        "authors": len(graph["authors"]),
        "categories": len(graph["categories"]),
        "nodes": len(nodes),
        "relationships": len(relationships),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps({"stats": stats}, ensure_ascii=False) + "\n")
        for row in nodes:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        for row in relationships:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return stats


def load_graph(path):
    # read the jsonl back into the dicts, one line at a time
    graph = new_graph()
    if not os.path.exists(path):
        return graph
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "labels" not in obj:
                continue  # stats line or a relationship (rebuilt from nodes on save)
            kind, _, key = obj["id"].partition(":")
            props = obj.get("properties", {})
            if kind == "paper":
                graph["papers"][key] = {
                    "title": props.get("title", ""),
                    "abstract": props.get("abstract", ""),
                    "authors": props.get("authors", ""),
                    "author_keys": props.get("author_keys", []),
                    "categories": props.get("categories", []),
                    "doi": props.get("doi", ""),
                    "journal_ref": props.get("journal_ref", ""),
                    "update_date": props.get("update_date", ""),
                }
            elif kind == "author":
                graph["authors"][key] = {
                    "name": props.get("name", key),
                    "paper_count": props.get("paper_count", 1),
                }
            elif kind == "category":
                graph["categories"][key] = props.get("paper_count", 0)

    return graph

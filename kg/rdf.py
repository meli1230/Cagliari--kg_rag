# serialize the in-memory graph to RDF (Turtle / TriG) for GraphDB.
# works on the {papers, authors, categories} dicts that graph.py builds.
# no third-party deps: literals and IRIs are escaped by hand.

import os
import re

from .config import DEFAULT_RDF_BASE

# arXiv papers get their real, dereferenceable URIs; authors/categories/vocab
# hang off the configurable base so you can rehost them under your own namespace.
ARXIV_ABS = "https://arxiv.org/abs/"

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# unreserved IRI chars (RFC 3987) + "/" ":" which are legal in a path; anything
# else in a local id gets percent-encoded so the IRI stays valid (old-style
# arXiv ids like "hep-ph/9901001" keep their slash, which is fine).
_SAFE_IRI = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~/:"
)


def _iri_segment(text):
    out = []
    for ch in text:
        if ch in _SAFE_IRI:
            out.append(ch)
        else:
            out.extend(f"%{b:02X}" for b in ch.encode("utf-8"))
    return "".join(out)


def _esc(text):
    # escape for a Turtle single-line quoted string ("...")
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


class _Vocab:
    def __init__(self, base):
        self.base = base.rstrip("/") + "/"
        self.vocab = self.base + "schema#"
        self.author_ns = self.base + "author/"
        self.category_ns = self.base + "category/"

    def paper(self, arxiv_id):
        return f"<{ARXIV_ABS}{_iri_segment(arxiv_id)}>"

    def author(self, key):
        return f"<{self.author_ns}{_iri_segment(key)}>"

    def category(self, name):
        return f"<{self.category_ns}{_iri_segment(name)}>"

    def header(self):
        return f"""@prefix rdf:      <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:      <http://www.w3.org/2001/XMLSchema#> .
@prefix dcterms:  <http://purl.org/dc/terms/> .
@prefix foaf:     <http://xmlns.com/foaf/0.1/> .
@prefix bibo:     <http://purl.org/ontology/bibo/> .
@prefix kg:       <{self.vocab}> .

# --- vocabulary (self-describing so GraphDB shows readable names) ---
kg:Paper    a rdfs:Class ; rdfs:label "Paper" .
kg:Author   a rdfs:Class ; rdfs:label "Author" ; rdfs:subClassOf foaf:Person .
kg:Category a rdfs:Class ; rdfs:label "Category" .

kg:arxivId      a rdf:Property ; rdfs:label "arXiv id" .
kg:inCategory   a rdf:Property ; rdfs:label "in category" ; rdfs:range kg:Category .
kg:authorList   a rdf:Property ; rdfs:label "author list" ; rdfs:comment "ordered rdf:List of authors" .
kg:authorString a rdf:Property ; rdfs:label "authors (raw)" .
kg:paperCount   a rdf:Property ; rdfs:label "paper count" ; rdfs:range xsd:integer .
"""


def _paper_block(v, pid, p):
    po = ['    kg:arxivId "%s"' % _esc(pid)]
    title = p.get("title") or ""
    if title:
        po.append('    dcterms:title "%s"' % _esc(title))
        po.append('    rdfs:label "%s"' % _esc(title))
    if p.get("abstract"):
        po.append('    dcterms:abstract "%s"' % _esc(p["abstract"]))

    date = p.get("update_date") or ""
    if ISO_DATE.match(date):
        po.append('    dcterms:date "%s"^^xsd:date' % date)
    elif date:
        po.append('    dcterms:date "%s"' % _esc(date))

    if p.get("doi"):
        po.append('    bibo:doi "%s"' % _esc(p["doi"]))
    if p.get("journal_ref"):
        po.append('    dcterms:bibliographicCitation "%s"' % _esc(p["journal_ref"]))
    if p.get("authors"):
        po.append('    kg:authorString "%s"' % _esc(p["authors"]))

    keys = p.get("author_keys") or []
    if keys:
        po.append("    dcterms:creator %s" % ", ".join(v.author(k) for k in keys))
        po.append("    kg:authorList ( %s )" % " ".join(v.author(k) for k in keys))

    cats = p.get("categories") or []
    if cats:
        po.append("    kg:inCategory %s" % ", ".join(v.category(c) for c in cats))

    head = f"{v.paper(pid)} a kg:Paper, bibo:AcademicArticle ;"
    return head + "\n" + " ;\n".join(po) + " ."


def _author_block(v, key, a):
    name = a.get("name") or key
    return (
        f"{v.author(key)} a kg:Author, foaf:Person ;\n"
        f'    foaf:name "{_esc(name)}" ;\n'
        f'    rdfs:label "{_esc(name)}" ;\n'
        f'    kg:paperCount {int(a.get("paper_count", 0))} .'
    )


def _category_block(v, name, count):
    return (
        f"{v.category(name)} a kg:Category ;\n"
        f'    rdfs:label "{_esc(name)}" ;\n'
        f"    kg:paperCount {int(count)} ."
    )


def save_rdf(graph, path, fmt="ttl", base=DEFAULT_RDF_BASE,
             graph_iri="http://example.org/arxiv/graph"):
    """Write the graph to `path` as Turtle (fmt='ttl') or TriG (fmt='trig').

    Returns the number of nodes serialized. Writes via a tmp file + rename so a
    crash can't leave a half-written file."""
    v = _Vocab(base)
    blocks = []
    for pid, p in graph["papers"].items():
        blocks.append(_paper_block(v, pid, p))
    for key, a in graph["authors"].items():
        blocks.append(_author_block(v, key, a))
    for name, count in graph["categories"].items():
        blocks.append(_category_block(v, name, count))

    body = "\n\n".join(blocks)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(v.header())
        if fmt == "trig":
            f.write(f"\n<{graph_iri}> {{\n\n{body}\n\n}}\n")
        else:
            f.write("\n\n" + body + "\n")
    os.replace(tmp, path)
    return len(blocks)

# arXiv RAG + Knowledge Graph

Builds a knowledge graph out of the arXiv metadata snapshot (deterministically) and
emits it as RDF (Turtle/TriG) for GraphDB or any triplestore.

Built to produce a small, reproducible benchmark for RAG question-answering:
a random sample of papers whose abstracts are the retrieval corpus, paired with a
metadata knowledge graph that complements the text - authorship and
category structure are not stated in the abstracts, so answering questions well needs
both sources. The sample is drawn with a fixed seed, so the whole dataset rebuilds
identically from one command.

Python 3, standard library only (nothing to `pip install`).

## Data source

The [arXiv metadata snapshot](https://www.kaggle.com/datasets/Cornell-University/arxiv)
- one JSON object per line, ~3.1M papers, ~5 GB. Not committed (too large); drop it at
`data/raw/arxiv-metadata-oai-snapshot.json`, or override the path in
[`kg_extraction/config.py`](kg_extraction/config.py) (`DEFAULT_INPUT`).

## Graph schema

Nodes (the conceptual model; the RDF IRIs and predicates are in [Output](#output))

| Type | IRI | Properties |
|---|---|---|
| `Paper` | `https://arxiv.org/abs/<arxiv_id>` | `arxiv_id`, `title`, `abstract`, `authors`, `categories`, `doi`, `journal_ref`, `update_date` |
| `Author` | `<base>/author/<key>` | `name`, `paper_count` |
| `Category` | `<base>/category/<name>` | `name`, `paper_count` |

Relationships

| Type | Direction | Properties |
|---|---|---|
| `AUTHORED` | Author → Paper | `position` (author order on the paper) |
| `IN_CATEGORY` | Paper → Category | - |

Authors are deduplicated by a coarse key: accent-stripped last name + first-name
initials (`author_key` in [`kg_extraction/utils.py`](kg_extraction/utils.py)), so "E. L. Berger" and
"Edward L. Berger" merge into one node. This occasionally merges two different
people who share a last name and initials - an accepted trade-off.

## Usage

Run as a module from the repo root (the one containing `kg_extraction/`):

```bash
# The RAG benchmark: 100 random AI/ML papers, reproducible via the seed
python -m kg_extraction.build_kg --sample 100 --categories cs.AI cs.LG --seed 42

# Ingest everything matching, no sampling (large)
python -m kg_extraction.build_kg --limit 0 --categories cs.AI cs.CL cs.LG

# Keyword filter, first 200 matches
python -m kg_extraction.build_kg --limit 200 --search "knowledge graph"
```

Flags:

| Flag | Meaning |
|---|---|
| `--sample N` | Randomly draw N papers from all matches (reservoir sampling, one pass). Reproducible: the same `--seed` always yields the same N papers. Overrides `--limit`. |
| `--seed S` | Random seed for `--sample` (default `42`). Change it to draw a different sample. |
| `--categories` | Category prefixes, space-separated (e.g. `cs.AI cs.LG`, or just `cs`). A paper matches if any of its categories starts with any prefix. |
| `--search` | Keyword that must appear in the title or abstract (case-insensitive). |
| `--limit N` | Stop after N matching papers. `0` = no limit. Note: the snapshot is in ascending arXiv-ID order, so a bounded run returns the oldest N, not the newest. Ignored when `--sample` is set. |
| `--format` | RDF serialization: `ttl` (Turtle, default) or `trig` (TriG, wraps the data in one named graph). |
| `--base` | Namespace base for author/category/vocabulary IRIs (default `http://example.org/arxiv/`, from `kg_extraction/config.py`). arXiv papers always use their real `https://arxiv.org/abs/` URIs. |
| `--papers [PATH]` | Also write the article records (the RAG corpus) as a flat table. `PATH` optional (defaults to the output path with a `.csv`/`.json` extension). See [Articles table](#articles-table-the-corpus). |
| `--papers-format` | `csv` (default) or `json`. |
| `--input` / `--output` | Override the default snapshot / RDF-output paths from `kg_extraction/config.py`. |

Papers with no abstract are always skipped. `Ctrl-C` during a run writes what's been
ingested so far.

## Output

An RDF file for a triplestore: **Turtle** (`.ttl`, default) or **TriG** (`.trig`, via
`--format trig`, which wraps everything in one named graph). `DEFAULT_OUTPUT` in the
config. The conceptual graph above maps onto standard vocabularies (Dublin Core, FOAF,
BIBO) so it's queryable without a custom ontology:

| Node / edge | RDF |
|---|---|
| `Paper` | `<https://arxiv.org/abs/{id}>` `a kg:Paper, bibo:AcademicArticle` |
| paper `title` / `abstract` / `update_date` | `dcterms:title` / `dcterms:abstract` / `dcterms:date`^^`xsd:date` |
| paper `doi` / `journal_ref` | `bibo:doi` / `dcterms:bibliographicCitation` (omitted when empty) |
| `Author` | `<…/author/{key}>` `a kg:Author, foaf:Person`; `foaf:name` |
| `Category` | `<…/category/{name}>` `a kg:Category`; `rdfs:label` |
| `AUTHORED` (with `position`) | `dcterms:creator` + ordered `kg:authorList ( … )` (order = position) |
| `IN_CATEGORY` | `kg:inCategory` |
| `paper_count` | `kg:paperCount`^^`xsd:integer` |

Papers use their real, dereferenceable arXiv URIs; authors/categories/vocabulary hang off
`--base`. Every node also carries `rdfs:label` so GraphDB's visual graph shows readable
names, and the file is self-describing (the `kg:` classes/properties are declared inline).
Paper nodes carry `dcterms:abstract`, so this one file is both the RAG corpus (the
abstract text to retrieve over) and the knowledge graph (the structure to reason over) —
no second file to keep in sync. Old-style arXiv ids with a slash (`hep-ph/9901001`) are
handled — every resource is emitted as a full IRI.

### Import into GraphDB

*Import → Upload RDF files* (or *Import → RDF from URL*), pick the `.ttl`/`.trig`,
optionally target a named graph, and import. Then, for example:

```sparql
PREFIX kg: <http://example.org/arxiv/schema#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
# papers in cs.LG and their authors
SELECT ?title ?author WHERE {
  ?p a kg:Paper ; dct:title ?title ;
     kg:inCategory <http://example.org/arxiv/category/cs.LG> ;
     dct:creator ?a .
  ?a foaf:name ?author .
}
```

## Articles table (the corpus)

Pass `--papers` to also emit the paper records as a flat one-row-per-article table —
the RAG corpus that pairs with the graph. CSV by default (opens in Excel / loads as a
DataFrame), or `--papers-format json` for a JSON array.

| Column | |
|---|---|
| `arxiv_id`, `url` | `url` is `https://arxiv.org/abs/<arxiv_id>` — **the join key**: it's exactly the `Paper` IRI in the RDF, so the table and the graph line up 1:1. |
| `title`, `abstract` | The retrieval text (title + abstract). |
| `authors` | Human-readable author string. |
| `author_keys`, `categories` | Multi-valued: JSON arrays, or `|`-joined in CSV. `author_keys`/`categories` are the graph's `Author`/`Category` keys, so you can walk from a retrieved row into the KG. |
| `update_date`, `doi`, `journal_ref` | Metadata (may be empty). |

So the two artifacts complement each other: the CSV/JSON is the text to retrieve over,
the RDF is the structure to reason over, joined on `arxiv_id`.

### Current build

The committed output is a reproducible 100-paper random sample of AI/ML
(`cs.AI`, `cs.LG`), seed `42`:

| | count |
|---|---|
| Papers | 100 |
| Authors | 433 |
| Categories | 45 |
| Nodes | 578 |
| Relationships | 725 |

Rebuild both artifacts identically with:

```bash
python -m kg_extraction.build_kg --sample 100 --categories cs.AI cs.LG --seed 42 \
    --output data/processed/knowledge_graph.ttl --papers data/processed/knowledge_graph.csv
```

## Design decisions


### 1. Goal

The target is a small corpus + knowledge graph that complement each other,
so that answering a question needs both the text and the structure.

### 2. Scope

The snapshot is ~3.1M papers / ~5 GB. We first scoped to the AI/ML/NLP slice
(`cs.AI`+`cs.CL`+`cs.LG`) - 444,205 papers. It builds deterministically in ~65s, but
444K papers is not "small, coherent" benchmark the task calls for. Even
`cs.AI` alone is 188,749 papers. 

### 3. LLM concept extraction: tried it, dropped it

We built an LLM semantic layer first (Ollama, `qwen2.5:7b`, with Gemini/OpenAI stubs):
per abstract it extracted `Concept` nodes plus `MENTIONS` and concept-to-concept
`RELATION` edges as structured JSON. It ran fine, but we removed it for two reasons:

- Scale. ~10s/paper on the local GPU (RTX 5050, 8 GB) × 444K papers ≈ 51 days.
  Cloud APIs (Gemini Flash / GPT-4o-mini) are faster and parallelizable but cost money
  (~$100–200 for the full slice) and need a key. This reason vanishes at 100 papers
  (~15 min locally), so it isn't why the layer is gone today.
- Redundancy (the real reason). Concepts pulled from the abstracts make the graph a
  subset of the corpus it's paired with. Metadata
  (authorship, categories) is not stated in the abstracts, so a metadata graph
  genuinely complements the corpus.

So the graph is deterministic and metadata-only. The language model still drives the
pipeline, but at query time: RAG retrieves abstracts (corpus) and walks the graph
(structure), and the model answers over both. The build stays LLM-free; the integration
lives in the query path.

### 4. Corpus vs KG boundary

The complementarity only holds if the corpus is the abstract text (title + abstract).
If the whole metadata record were treated as "the document," the graph would be redundant
with it again. So: corpus = abstracts; KG = authorship + category structure.

### 5. Sampling

The task allowed hand-curation, but we chose an automated, reproducible sample for
the reproducibility criterion: 100 papers drawn by reservoir sampling with a fixed seed
(`--sample 100 --seed 42`). Same seed == identical dataset. change the seed for a
fresh draw. `cs.AI`+`cs.LG` = "AI and ML".

### 6. Connectivity check

Concern: 100 random papers might barely link up, hurting multi-hop KG reasoning. We
measured the random baseline against three themed samples (`--search` inside `cs.AI`+
`cs.LG`, same seed). Two papers are "linked" if they share an author, or an author/category:

| sample | papers | authors | shared authors | components (via authors) | biggest (authors) | components (auth+cat) |
|---|---|---|---|---|---|---|
| random (baseline) | 100 | 433 | 25 | 67 | 33 | 1 |
| "reinforcement learning" | 100 | 488 | 33 | 57 | 41 | 1 |
| "graph neural network" | 100 | 409 | 27 | 66 | 21 | 1 |
| "transformer" | 100 | 437 | 15 | 80 | 16 | 1 |

What we observed:

- Via categories, every sample is already one connected component - all papers share
  the `cs.AI`/`cs.LG` hub nodes. Complete, but shallow (two coarse hubs).
- Via authors, connectivity is modest and theme-dependent. "reinforcement learning"
  is the densest (a tighter research community); "transformer" is sparser than random
  (a broad buzzword spanning unrelated groups). Themed sampling is not a reliable
  connectivity win - it depends entirely on how cohesive the theme's community is.
- A caveat that changes the read (see 7): the author links are partly
  spurious.

Decision: keep the unbiased random baseline. It is already category-complete, and
themed sampling buys little real author connectivity while biasing the corpus.

### 7. Author entity resolution

Authors are keyed by a coarse id: accent-stripped surname + first-name initials
(`author_key`). This deliberately merges `E. L. Berger` and `Edward L. Berger`, but it
also merges different people who share surname + initials. In the 100-paper sample the
"most prolific author" is `li_s` with 6 papers - almost certainly several distinct
researchers collapsed into one node. Consequences:

- The author-based connectivity in decision 6 is inflated; real co-authorship links
  are fewer than the table suggests.
- This is a concrete security / robustness issue for the KG-RAG pipeline: a query
  like "what else did the author of paper X write?" can return other people's work, and
  ambiguous names are an adversarial handle. It belongs in the security discussion, with
  options (finer keys using full given names or blocking on
  name+affiliation) and their precision/recall trade-offs.

## Layout

```
kg_extraction/        data extraction + KG-building pipeline
  build_kg.py         CLI entry point (run as `python -m kg_extraction.build_kg`)
  eda.py              exploratory analysis of the raw arXiv snapshot
  config.py           paths (relative to data/) + pretty-print threshold
  utils.py            text cleanup + author-key normalization
  arxiv.py            streaming JSONL reader + reproducible sampling
  graph.py            in-memory graph model
  rdf.py              RDF export (Turtle/TriG) for GraphDB
  papers.py           article-table export (CSV/JSON), the RAG corpus
data/
  raw/                arXiv snapshot (not committed, see Data source)
  processed/          committed knowledge_graph.ttl / knowledge_graph.csv
webapp/               Flask demo app (currently a stub - RAG pipeline not wired in yet)
  app.py
  templates/
  static/
```

# arXiv Knowledge Graph

Builds a property graph out of the arXiv metadata snapshot (deterministically).

Built to produce a small, reproducible benchmark for RAG question-answering:
a random sample of papers whose abstracts are the retrieval corpus, paired with a
metadata knowledge graph that complements the text - authorship and
category structure are not stated in the abstracts, so answering questions well needs
both sources. The sample is drawn with a fixed seed, so the whole dataset rebuilds
identically from one command.

Python 3, standard library only (nothing to `pip install`).

## Data source

The [arXiv metadata snapshot](https://www.kaggle.com/datasets/Cornell-University/arxiv)
- one JSON object per line, ~3.1M papers, ~5 GB. The path is set in
[`kg/config.py`](kg/config.py) (`DEFAULT_INPUT`).

## Graph schema

Nodes

| Label | Key | Properties |
|---|---|---|
| `Paper` | `paper:<arxiv_id>` | `arxiv_id`, `title`, `abstract`, `authors`, `author_keys`, `categories`, `doi`, `journal_ref`, `update_date` |
| `Author` | `author:<key>` | `name`, `paper_count` |
| `Category` | `category:<name>` | `name`, `paper_count` |

Relationships

| Type | Direction | Properties |
|---|---|---|
| `AUTHORED` | Author → Paper | `position` (author order on the paper) |
| `IN_CATEGORY` | Paper → Category | - |

Authors are deduplicated by a coarse key: accent-stripped last name + first-name
initials (`author_key` in [`kg/utils.py`](kg/utils.py)), so "E. L. Berger" and
"Edward L. Berger" merge into one node. This occasionally merges two different
people who share a last name and initials - an accepted trade-off.

## Usage

Run from this folder (the one containing `knowledge_graph.py` and the `kg/` package):

```bash
# The RAG benchmark: 100 random AI/ML papers, reproducible via the seed
python knowledge_graph.py --sample 100 --categories cs.AI cs.LG --seed 42

# Ingest everything matching, no sampling (large)
python knowledge_graph.py --limit 0 --categories cs.AI cs.CL cs.LG

# Keyword filter, first 200 matches
python knowledge_graph.py --limit 200 --search "knowledge graph"
```

Flags:

| Flag | Meaning |
|---|---|
| `--sample N` | Randomly draw N papers from all matches (reservoir sampling, one pass). Reproducible: the same `--seed` always yields the same N papers. Overrides `--limit`. |
| `--seed S` | Random seed for `--sample` (default `42`). Change it to draw a different sample. |
| `--categories` | Category prefixes, space-separated (e.g. `cs.AI cs.LG`, or just `cs`). A paper matches if any of its categories starts with any prefix. |
| `--search` | Keyword that must appear in the title or abstract (case-insensitive). |
| `--limit N` | Stop after N matching papers. `0` = no limit. Note: the snapshot is in ascending arXiv-ID order, so a bounded run returns the oldest N, not the newest. Ignored when `--sample` is set. |
| `--resume` | Load the existing output and skip papers already in it, then keep going. |
| `--input` / `--output` | Override the default paths from `kg/config.py`. |

Papers with no abstract are always skipped. `Ctrl-C` during a run saves what's been
ingested so far.

## Output

A [JSON Lines](https://jsonlines.org/) file (`.jsonl`, `DEFAULT_OUTPUT` in the config):
**one JSON object per line**. The first line is a `stats` summary, then one line per
node, then one line per relationship:

```jsonl
{"stats": {"papers": ..., "authors": ..., "categories": ..., "nodes": ..., "relationships": ..., "generated": "..."}}
{"id": "paper:2203.02997", "labels": ["Paper"], "properties": { ... }}
{"id": "author:gokcesu_k", "labels": ["Author"], "properties": { ... }}
{"id": "category:cs.LG", "labels": ["Category"], "properties": { ... }}
{"source": "author:gokcesu_k", "target": "paper:2203.02997", "type": "AUTHORED", "properties": {"position": 1}}
{"source": "paper:2203.02997", "target": "category:cs.LG", "type": "IN_CATEGORY", "properties": {}}
```

Node lines have a `labels` key; relationship lines have `source`/`target`. JSON Lines is
streamable (read it line by line, no need to load the whole file) and appendable, and it
imports directly into Neo4j via `apoc.import.json`.

Paper nodes carry the `abstract`, so this one file is both the RAG corpus (the
abstract text to retrieve over) and the knowledge graph (the structure to reason
over) - no second file to keep in sync.

> A full-category run (no `--sample`) can produce a large file, but because it's line
> delimited you can stream it without loading it all into memory.

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

Rebuild it identically with:

```bash
python knowledge_graph.py --sample 100 --categories cs.AI cs.LG --seed 42
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
knowledge_graph.py   CLI entry point
kg/
  config.py          paths + pretty-print threshold
  utils.py           text cleanup + author-key normalization
  arxiv.py           streaming JSONL reader + reproducible sampling
  graph.py           graph model + JSONL save/load
```

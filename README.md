# arXiv RAG + Knowledge Graph

A KG-augmented RAG assistant over a reproducible slice of arXiv. It answers questions
like "give me the abstract of paper X" or "what's the most recent paper?" by combining
two retrieval paths: semantic search over abstracts and SPARQL queries over a
metadata knowledge graph.

The project has two halves:

1. Build (`kg_extraction/`) - turns the arXiv metadata snapshot into a knowledge graph
   deterministically, emitting RDF (Turtle/TriG) for GraphDB plus a flat article table.
   Pure Python 3 standard library, no LLM involved.
2. Query (`rag/`, `webapp/`) - a hybrid pipeline that routes a question to the graph
   and/or the vector index, then has an LLM answer over the retrieved context. Runs as a
   CLI or a Flask chat app.

The two artifacts complement each other by design: abstracts are the retrieval corpus,
and the graph holds what abstracts don't say (authorship, categories, dates, DOIs), so
answering well needs both. The sample is drawn with a fixed seed, so the whole dataset
rebuilds identically from one command.

## Layout

```
kg_extraction/        data extraction + KG-building pipeline (stdlib only)
  build_kg.py         CLI entry point (run as `python -m kg_extraction.build_kg`)
  eda.py              exploratory analysis of the raw arXiv snapshot
  config.py           paths (relative to data/) + pretty-print threshold
  utils.py            text cleanup + author-key normalization
  arxiv.py            streaming JSONL reader + reproducible sampling
  graph.py            in-memory graph model
  rdf.py              RDF export (Turtle/TriG) for GraphDB
  papers.py           article-table export (CSV/JSON), the RAG corpus
rag/                  the query-time pipeline
  build_index.py      CLI: builds the FAISS index from the article CSV
  main.py             CLI: interactive question loop
  pipeline.py         orchestrator - routing, KG lookup, retrieval, answer generation
  query_router.py     LLM router: question -> KG query type (or none)
  kgqueries.py        the canned SPARQL queries + their enum
  kg_client.py        loads the .ttl with rdflib, runs SELECT queries locally
  retriever.py        embedding + FAISS index, exact/partial/semantic title matching
  models.py           Article / RetrievedArticle dataclasses
  settings.py         env-var helper (currently unused, see Known gaps)
data/
  raw/                arXiv snapshot (not committed, see Data source)
  processed/          committed knowledge_graph.ttl / knowledge_graph.csv
    rag_index/        committed FAISS index + article payloads
webapp/               Flask chat app (wired to the full pipeline)
  app.py              routes: GET / and POST /ask
  templates/
  static/
```

## Quick start

```bash
pip install -r requirements.txt

# Provide an OpenAI-compatible key (a .env file at the repo root works - python-dotenv
# loads it automatically)
echo "OPENAI_API_KEY=sk-..." > .env
echo "OPENAI_MODEL=gpt-4o-mini" >> .env

python -m rag.build_index            # embed the corpus -> data/processed/rag_index/
python -m rag.main                   # ask questions in the terminal
python webapp/app.py                 # or use the chat UI at http://localhost:5000
```

The committed `data/processed/` already contains the graph, the article table, and a
prebuilt FAISS index, so you can skip straight to `rag.main` without downloading the
5 GB snapshot. Rebuilding the index is only needed if you regenerate the corpus.

### Environment variables

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY` / `LLM_API_KEY` | API key. Either name works; `LLM_API_KEY` wins. Required - the pipeline raises on startup without one. |
| `OPENAI_MODEL` | Chat model for routing, title selection, and answering (default `gpt-4o-mini`). |

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

## Building the knowledge graph

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

An RDF file for a triplestore: Turtle (`.ttl`, default) or TriG (`.trig`, via
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
abstract text to retrieve over) and the knowledge graph (the structure to reason over) -
no second file to keep in sync. Old-style arXiv ids with a slash (`hep-ph/9901001`) are
handled - every resource is emitted as a full IRI.

### Import into GraphDB

Import → Upload RDF files (or Import → RDF from URL), pick the `.ttl`/`.trig`,
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

GraphDB is optional - the query pipeline doesn't need a running triplestore. It loads
the same `.ttl` into an in-process rdflib graph
([`rag/kg_client.py`](rag/kg_client.py)) and runs SPARQL against that.

## Articles table (the corpus)

Pass `--papers` to also emit the paper records as a flat one-row-per-article table -
the RAG corpus that pairs with the graph. CSV by default (opens in Excel / loads as a
DataFrame), or `--papers-format json` for a JSON array.

| Column | |
|---|---|
| `arxiv_id`, `url` | `url` is `https://arxiv.org/abs/<arxiv_id>` - the join key: it's exactly the `Paper` IRI in the RDF, so the table and the graph line up 1:1. |
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

Then re-embed the corpus (`python -m rag.build_index`) so the index matches the new CSV.

## The query pipeline

The interesting part: a question can be answered from the text, from the graph, or from
both. [`ArticleRAGPipeline.answer_question`](rag/pipeline.py) decides which.

```
question
   │
   ▼
QuestionRouter (LLM)  ──►  {query_type, requested_title}
   │
   ├── query_type != none ──►  canned SPARQL on the local .ttl (rdflib)
   │                              │
   │                              ├── titles found ──►  LLM picks the best title
   │                              │                          │
   │                              └── no titles ─────────┐   │
   │                                                     │   │
   └── query_type == none ──►  LLM extracts a title ─────┤   │
                                                         ▼   ▼
                                            ArticleRetriever (FAISS)
                                                         │
                                                         ▼
                                       LLM returns the stored abstract, verbatim
```

### 1. Routing

[`rag/query_router.py`](rag/query_router.py) asks the model to classify the question into
one of five structured conditions, or `none`. It returns JSON
(`{query_type, requested_title, reason}`) and never generates SPARQL itself - the queries
are fixed and live in [`rag/kgqueries.py`](rag/kgqueries.py). A question only routes to the
graph when it explicitly states the condition; anything else (including a plain "give me
the abstract of X") falls through to `none` and goes straight to retrieval.

| `query_type` | Triggered by | SPARQL finds |
|---|---|---|
| `single_paper_author` | "written by an author with only one paper" | papers whose author has `kg:paperCount 1` |
| `published_in_2026` | "published in 2026" | papers whose `dcterms:date` starts with `2026` |
| `stat_ml_category` | "in the stat.ML category" | papers `kg:inCategory` the `stat.ML` node |
| `most_recent` | "newest / latest / most recent" | top paper by `dcterms:date DESC`, `LIMIT 1` |
| `has_doi` | "must have a DOI" | papers with a `bibo:doi` |
| `none` | everything else | - (skips the graph) |

These are exactly the questions the abstracts cannot answer, which is the point: the
graph contributes the structure, the corpus contributes the text.

### 2. Title selection

A KG query returns titles, not answers. If it returns more than one (capped at
`maximum_kg_titles=100`), the pipeline asks the model to pick the single title that best
fits the question, constrained to the candidate list - it may not invent or edit a title,
and falls back to the first candidate if the question doesn't disambiguate. If the router
supplied an explicit title that matches a candidate, that wins without an LLM call.

If the KG path yields nothing, the pipeline degrades to pure RAG rather than failing.

### 3. Retrieval

[`rag/retriever.py`](rag/retriever.py) - `sentence-transformers/all-MiniLM-L6-v2`
embeddings in a FAISS `IndexFlatIP`. Vectors are L2-normalized, so inner product is
cosine similarity. Documents embed title + abstract + metadata
(`Article.text_for_embedding`).

Matching is tiered:

| `match_type` | How | Score |
|---|---|---|
| `exact_title` | Normalized title (casefolded, punctuation stripped) matches exactly. Short-circuits - no vector search at all. | `1.0` |
| `partial_title` | One normalized title contains the other. | cosine + `0.20` boost |
| `semantic` | Nearest neighbours from FAISS. | cosine |

`generate_abstract` pulls `top_k=3` candidates and refuses to answer unless the best hit
is an exact title match or clears `minimum_similarity=0.35`, so an off-corpus question
gets "No matching article was found in the database." instead of a hallucination.

### 4. Answering

The final call hands the model the retrieved articles and asks it to return the stored
abstract verbatim - no summarizing, rewriting, or extending. The system prompt
explicitly marks retrieved article content as untrusted data, not instructions, and
tells the model to ignore any commands embedded in a title, abstract, or metadata field.
That's a deliberate prompt-injection guard: the corpus is third-party text, and abstracts
are an obvious injection surface.

Answers carry a provenance footer, so you can always see which path produced them:

```
Title: ...
Author: ...
Abstract: ...

---
Knowledge Graph used: Yes
SPARQL query used: most_recent
Resolved paper title: ...
```

### Interfaces

- CLI - `python -m rag.main`. Interactive loop; `exit` or `quit` to stop.
- Web - `python webapp/app.py`, then http://localhost:5000. A chat UI
  (`GET /`) posting to a JSON endpoint (`POST /ask` → `{"answer": ...}`). The retriever,
  graph, and pipeline are constructed once at import, so the first request is warm but
  startup pays the model-load and TTL-parse cost.

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

It also leaks into the `single_paper_author` KG query: `kg:paperCount 1` means "one paper
under this coarse key," which over-counts prolific-but-ambiguous names as one-paper
authors and vice versa.

### 8. Canned SPARQL, not generated SPARQL

The router picks from five fixed queries instead of writing SPARQL from the question.
Letting an LLM emit SPARQL against the graph is more flexible but opens an injection
surface (a crafted question producing a query that dumps or, against a live endpoint with
write access, mutates the store) and fails in ways that are hard to detect - a subtly
wrong query returns plausible rows. Fixed queries make the KG path auditable and total:
every route is a query someone reviewed. The cost is coverage, questions outside those
five conditions get no graph support and fall back to pure RAG.

### 9. Untrusted corpus content

Retrieved abstracts are third-party text that reaches the model inside its context, which
is textbook indirect prompt injection. Mitigations in place: retrieved content is fenced
in `<retrieved_articles>` tags, the system prompt declares it data rather than
instructions, generation is pinned to `temperature=0.0`, and the model is told to return
stored text verbatim rather than act on it. This is defense-in-depth, not a proof - the
robust version of this argument is that the pipeline has no tools and no write path, so a
successful injection can only corrupt one answer.

## Running
The `.env` file should have the following structure:
```dotenv
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=gpt-4o-mini
```

In order to run the app in the terminal:
- `python -m rag.build_index` -> for the embeddings
- `python -m rag.main` -> to run the app

For running the front-end, add to the `.env` file: 
```dotenv
FLASK_APP=webapp.app
```

And to run the app on your browser:
- `flask run` -> to run the front-end

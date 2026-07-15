from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# arXiv metadata snapshot (Kaggle), not committed - see README "Data source".
DEFAULT_INPUT = str(DATA_DIR / "raw" / "arxiv-metadata-oai-snapshot.json")
# RDF output (Turtle) for GraphDB.
DEFAULT_OUTPUT = str(DATA_DIR / "processed" / "knowledge_graph.ttl")

# namespace base for authors, categories and the kg: vocabulary.
# arXiv papers always use their real https://arxiv.org/abs/ URIs.
DEFAULT_RDF_BASE = "http://example.org/arxiv/"

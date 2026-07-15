# entry point: sample/filter papers from the arxiv snapshot and write the graph
# as RDF (Turtle/TriG) for GraphDB. usage, flags and layout are in README.md

import argparse
import os
import time

from kg_extraction.arxiv import iter_papers, sample_papers
from kg_extraction.config import DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_RDF_BASE
from kg_extraction.graph import graph_stats, ingest_paper, new_graph
from kg_extraction.papers import save_papers
from kg_extraction.rdf import save_rdf


def main():
    parser = argparse.ArgumentParser(description="Build an RDF knowledge graph from arXiv metadata.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="RDF output path (.ttl/.trig)")
    parser.add_argument("--format", choices=["ttl", "trig"], default="ttl",
                        help="RDF serialization: Turtle (default) or TriG")
    parser.add_argument("--base", default=DEFAULT_RDF_BASE,
                        help="namespace base for author/category/vocab IRIs")
    parser.add_argument("--papers", nargs="?", const="", default=None,
                        help="also write the article records (the RAG corpus); optional PATH "
                             "(default: output with a .csv/.json extension)")
    parser.add_argument("--papers-format", choices=["csv", "json"], default="csv",
                        help="article-table format (default: csv)")
    parser.add_argument("--limit", type=int, default=25, help="max papers this run; 0 = no limit")
    parser.add_argument("--sample", type=int, default=None,
                        help="randomly sample N papers from the matches (reproducible with --seed)")
    parser.add_argument("--seed", type=int, default=42, help="random seed for --sample")
    parser.add_argument("--categories", nargs="*", default=None,
                        help="category prefixes, e.g. cs.AI cs.LG hep-ph (or just cs)")
    parser.add_argument("--search", default=None, help="keyword that must appear in title/abstract")
    args = parser.parse_args()

    graph = new_graph()
    processed = 0
    start = time.time()
    try:
        if args.sample:
            # scan all matches, keep a reproducible random N, then ingest them
            print(f"Sampling {args.sample} random papers (seed={args.seed})...")
            for paper in sample_papers(args.input, args.categories, args.search, args.sample, args.seed):
                ingest_paper(graph, paper)
                processed += 1
        else:
            for paper in iter_papers(args.input, args.categories, args.search, args.limit, set()):
                ingest_paper(graph, paper)
                processed += 1
                if processed % 10_000 == 0:
                    rate = processed / (time.time() - start)
                    print(f"  {processed:,} papers ingested ({rate:,.0f}/s)")
    except KeyboardInterrupt:
        print("\nInterrupted — saving what we have...")

    save_rdf(graph, args.output, fmt=args.format, base=args.base)
    stats = graph_stats(graph)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.0f}s: {processed} papers this run.")
    print(f"RDF ({args.format}): {stats['nodes']:,} nodes, "
          f"{stats['relationships']:,} relationships -> {args.output}")
    print(f"  papers={stats['papers']:,} authors={stats['authors']:,} "
          f"categories={stats['categories']:,}")

    if args.papers is not None:
        papers_path = args.papers or os.path.splitext(args.output)[0] + "." + args.papers_format
        n = save_papers(graph, papers_path, fmt=args.papers_format)
        print(f"Articles ({args.papers_format}): {n:,} rows -> {papers_path}")


if __name__ == "__main__":
    main()

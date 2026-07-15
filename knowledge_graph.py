# entry point: sample/filter papers from the arxiv snapshot and write the graph json.
# usage examples, flags and the package layout are in README.md

import argparse
import time

from kg.arxiv import iter_papers, sample_papers
from kg.config import DEFAULT_INPUT, DEFAULT_OUTPUT
from kg.graph import ingest_paper, load_graph, new_graph, save_graph


def main():
    parser = argparse.ArgumentParser(description="Build a knowledge graph from arXiv metadata.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=25, help="max papers this run; 0 = no limit")
    parser.add_argument("--sample", type=int, default=None,
                        help="randomly sample N papers from the matches (reproducible with --seed)")
    parser.add_argument("--seed", type=int, default=42, help="random seed for --sample")
    parser.add_argument("--categories", nargs="*", default=None,
                        help="category prefixes, e.g. cs.AI cs.LG hep-ph (or just cs)")
    parser.add_argument("--search", default=None, help="keyword that must appear in title/abstract")
    parser.add_argument("--resume", action="store_true",
                        help="load existing output and continue where the last run stopped")
    args = parser.parse_args()

    graph = load_graph(args.output) if args.resume else new_graph()
    skip_ids = set(graph["papers"])
    if skip_ids:
        print(f"Resuming: skipping {len(skip_ids)} already-processed papers")

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
            for paper in iter_papers(args.input, args.categories, args.search, args.limit, skip_ids):
                ingest_paper(graph, paper)
                processed += 1
                if processed % 10_000 == 0:
                    rate = processed / (time.time() - start)
                    print(f"  {processed:,} papers ingested ({rate:,.0f}/s)")
    except KeyboardInterrupt:
        print("\nInterrupted — saving what we have...")

    stats = save_graph(graph, args.output)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.0f}s: {processed} papers this run.")
    print(f"Graph: {stats['nodes']:,} nodes, {stats['relationships']:,} relationships -> {args.output}")
    print(f"  papers={stats['papers']:,} authors={stats['authors']:,} "
          f"categories={stats['categories']:,}")


if __name__ == "__main__":
    main()

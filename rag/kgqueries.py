from __future__ import annotations

from enum import Enum


class KGQueryType(str, Enum):
    SINGLE_PAPER_AUTHOR = "single_paper_author"
    PUBLISHED_IN_2026 = "published_in_2026"
    STAT_ML_CATEGORY = "stat_ml_category"
    MOST_RECENT = "most_recent"
    HAS_DOI = "has_doi"
    NONE = "none"


SPARQL_QUERIES: dict[KGQueryType, str] = {
    KGQueryType.SINGLE_PAPER_AUTHOR: """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {
    ?paper a kg:Paper;
        dcterms:title ?title;
        dcterms:creator ?author.

    ?author a kg:Author;
        kg:paperCount 1.
}
ORDER BY ?title
""".strip(),

    KGQueryType.PUBLISHED_IN_2026: """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {
    ?paper a kg:Paper;
        dcterms:title ?title;
        dcterms:date ?date.

    FILTER(STRSTARTS(STR(?date), "2026"))
}
ORDER BY DESC(?date)
""".strip(),

    KGQueryType.STAT_ML_CATEGORY: """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {
    ?paper a kg:Paper;
        dcterms:title ?title;
        kg:inCategory ?category.

    ?category a kg:Category;
        rdfs:label "stat.ML".
}
ORDER BY ?title
""".strip(),

    KGQueryType.MOST_RECENT: """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT ?title
WHERE {
    ?paper a kg:Paper;
        dcterms:title ?title;
        dcterms:date ?date.
}
ORDER BY DESC(?date)
LIMIT 1
""".strip(),

    KGQueryType.HAS_DOI: """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX bibo: <http://purl.org/ontology/bibo/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {
    ?paper a kg:Paper;
        dcterms:title ?title;
        bibo:doi ?doi.
}
ORDER BY ?title
""".strip(),
}
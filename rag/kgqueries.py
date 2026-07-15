from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from rdflib import Graph, Literal

logger = logging.getLogger(__name__)


@dataclass
class KGQueryResult:
    query_name: str
    titles: list[str]
    sparql: str


class KGQueryEngine:
    SUPPORTED_QUERIES = {
        "paper_by_author_and_year",
        "papers_by_year",
        "papers_by_category",
        "latest_paper",
        "papers_by_single_paper_authors",
    }

    def __init__(self, ttl_path: str | Path) -> None:
        self.ttl_path = Path(ttl_path)

        if not self.ttl_path.exists():
            raise FileNotFoundError(f"Knowledge graph file not found: {self.ttl_path}")

        self.graph = Graph()
        self.graph.parse(self.ttl_path, format="turtle")

        logger.info("Loaded knowledge graph with %d triples from %s", len(self.graph), self.ttl_path)

    @staticmethod
    def _literal(value: str) -> str:
        return Literal(value).n3()

    def build_query(self, query_name: str, parameters: dict[str, Any] | None = None) -> str:
        parameters = parameters or {}

        if query_name == "paper_by_author_and_year":
            return self._paper_by_author_and_year(
                author=str(parameters.get("author", "")),
                year=str(parameters.get("year", "")),
            )

        if query_name == "papers_by_year":
            return self._papers_by_year(
                year=str(parameters.get("year", "")),
            )

        if query_name == "papers_by_category":
            return self._papers_by_category(
                category=str(parameters.get("category", "")),
            )

        if query_name == "latest_paper":
            return self._latest_paper()

        if query_name == "papers_by_single_paper_authors":
            return self._papers_by_single_paper_authors()

        raise ValueError(f"Unsupported query name: {query_name}")

    def execute(self, query_name: str, parameters: dict[str, Any] | None = None) -> KGQueryResult:
        sparql = self.build_query(query_name=query_name, parameters=parameters)
        logger.info("Executing SPARQL query template: %s", query_name,)
        logger.debug("Generated SPARQL:\n%s", sparql)

        rows = self.graph.query(sparql)
        titles = []

        for row in rows:
            title = getattr(row, "title", None)

            if title is not None:
                titles.append(str(title))

        unique_titles = list(dict.fromkeys(titles))

        logger.info("SPARQL query '%s' returned %d title(s)", query_name, len(unique_titles))

        return KGQueryResult(query_name=query_name, titles=unique_titles, sparql=sparql)

    def _paper_by_author_and_year(self, author: str, year: str) -> str:
        if not author.strip():
            raise ValueError("The author parameter is required.")

        if not year.strip():
            raise ValueError("The year parameter is required.")

        author_literal = self._literal(author.strip())
        year_literal = self._literal(year.strip())

        return f"""
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {{
    ?paper a kg:Paper ;
           dcterms:title ?title ;
           dcterms:date ?date ;
           dcterms:creator ?authorResource .

    ?authorResource a kg:Author ;
                    foaf:name ?authorName .

    FILTER(
        CONTAINS(
            LCASE(STR(?authorName)),
            LCASE(STR({author_literal}))
        )
    )

    FILTER(
        STRSTARTS(
            STR(?date),
            STR({year_literal})
        )
    )
}}
""".strip()

    def _papers_by_year(
        self,
        year: str,
    ) -> str:
        # find papers published in a particular year
        if not year.strip():
            raise ValueError("The year parameter is required.")

        year_literal = self._literal(year.strip())

        return f"""
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {{
    ?paper a kg:Paper ;
           dcterms:title ?title ;
           dcterms:date ?date .

    FILTER(
        STRSTARTS(
            STR(?date),
            STR({year_literal})
        )
    )
}}
ORDER BY ?title
""".strip()

    def _papers_by_category(
        self,
        category: str,
    ) -> str:
        # find papers belonging to an arXiv category

        if not category.strip():
            raise ValueError("The category parameter is required.")

        category_literal = self._literal(category.strip())

        return f"""
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {{
    ?paper a kg:Paper ;
           dcterms:title ?title ;
           kg:inCategory ?categoryResource .

    ?categoryResource a kg:Category ;
                      rdfs:label ?categoryLabel .

    FILTER(
        LCASE(STR(?categoryLabel))
        =
        LCASE(STR({category_literal}))
    )
}}
ORDER BY ?title
""".strip()

    @staticmethod
    def _latest_paper() -> str:
        # find the most recently published paper
        return """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT ?title
WHERE {
    ?paper a kg:Paper ;
           dcterms:title ?title ;
           dcterms:date ?date .
}
ORDER BY DESC(?date)
LIMIT 1
""".strip()

    @staticmethod
    def _papers_by_single_paper_authors() -> str:
        # find authors that have exactly one paper
        return """
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX kg: <http://example.org/arxiv/schema#>

SELECT DISTINCT ?title
WHERE {
    ?paper a kg:Paper ;
           dcterms:title ?title ;
           dcterms:creator ?author .

    ?author a kg:Author ;
            kg:paperCount 1 .
}
ORDER BY ?title
""".strip()
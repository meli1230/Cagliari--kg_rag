from __future__ import annotations

from pathlib import Path

from rdflib import Graph


class LocalKnowledgeGraph:
    """
    Loads a Turtle knowledge graph and executes SPARQL queries locally.
    """

    def __init__(
        self,
        ttl_path: str | Path,
    ) -> None:
        self.ttl_path = Path(ttl_path)

        if not self.ttl_path.exists():
            raise FileNotFoundError(
                f"Knowledge graph not found: {self.ttl_path}"
            )

        self.graph = Graph()

        self.graph.parse(
            source=str(self.ttl_path),
            format="turtle",
        )

        print(
            f"Loaded {len(self.graph)} RDF triples "
            f"from {self.ttl_path}."
        )

    def execute_select(
        self,
        sparql_query: str,
    ) -> list[dict[str, str]]:
        """
        Execute a local SPARQL SELECT query.

        Returns rows as dictionaries such as:
        {
            "title": "Paper title"
        }
        """
        try:
            query_result = self.graph.query(
                sparql_query
            )
        except Exception as error:
            raise RuntimeError(
                "The local SPARQL query failed."
            ) from error

        rows: list[dict[str, str]] = []

        for row in query_result:
            row_data: dict[str, str] = {}

            for variable, value in row.asdict().items():
                if value is not None:
                    row_data[str(variable)] = str(value)

            rows.append(row_data)

        return rows

    def get_titles(
        self,
        sparql_query: str,
    ) -> list[str]:
        """
        Execute a query and extract unique values of ?title.
        """
        rows = self.execute_select(
            sparql_query
        )

        titles: list[str] = []
        seen: set[str] = set()

        for row in rows:
            title = row.get(
                "title",
                "",
            ).strip()

            normalized_title = title.casefold()

            if (
                title
                and normalized_title not in seen
            ):
                titles.append(title)
                seen.add(normalized_title)

        return titles
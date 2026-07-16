from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SelectionType = Literal[
    "single",
    "latest",
    "oldest",
    "most_relevant",
]


@dataclass
class PaperQueryIntent:
    title: str | None = None
    author: str | None = None
    category: str | None = None
    year: int | None = None
    selection: SelectionType = "single"
    requested_information: str = "abstract"


@dataclass
class Article:
    article_id: str
    title: str
    abstract: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def text_for_embedding(self) -> str:
        metadata_text = "\n".join(
            f"{key}: {value}"
            for key, value in self.metadata.items()
            if value is not None
        )

        parts = [
            f"Article title: {self.title}",
            f"Abstract: {self.abstract}",
        ]

        if metadata_text:
            parts.append(f"Metadata:\n{metadata_text}")

        return "\n".join(parts)


@dataclass
class RetrievedArticle:
    article: Article
    similarity_score: float
    match_type: str
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from rag.kgqueries import KGQueryType


@dataclass
class QueryRoute:
    query_type: KGQueryType
    requested_title: str | None
    reason: str


def _extract_json_object(text: str) -> dict:
    """
    Extract a JSON object from an LLM response.
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            flags=re.DOTALL,
        )

        if not match:
            raise ValueError(
                "The routing response did not contain JSON."
            )

        return json.loads(match.group(0))


class QuestionRouter:
    def __init__(
        self,
        client: OpenAI,
        model_name: str,
    ) -> None:
        self.client = client
        self.model_name = model_name

    def route(
        self,
        question: str,
    ) -> QueryRoute:
        """
        Determine whether the question can use a predefined KG query.

        If it cannot, extract the paper title or title-like search
        description for direct RAG retrieval.
        """
        system_prompt = """
You route questions for an academic-paper assistant.

The user always wants the abstract of a paper.

Choose exactly one query type:

- single_paper_author:
  Use when the requested paper was written by an author who has
  exactly one paper in the knowledge graph.

- published_in_2026:
  Use when the requested paper was published in 2026.

- stat_ml_category:
  Use when the requested paper belongs to the stat.ML category.

- most_recent:
  Use when the user requests the newest, latest, or most recent paper.

- has_doi:
  Use when the requested paper must have a DOI.

- none:
  Use when none of the above structured conditions are requested.
  This includes questions that directly provide a paper title or
  describe a paper using information that the available graph queries
  cannot answer.

Do not generate SPARQL.

Return valid JSON with exactly these fields:

{
  "query_type": "one of the values above",
  "requested_title": "explicit paper title or null",
  "reason": "brief routing explanation"
}

Rules:

1. Only use a KG query when the question explicitly contains the
   corresponding condition.
2. Do not assume a condition that the user did not mention.
3. Preserve an explicitly provided paper title.
4. Return query_type "none" for normal title-based RAG questions.
""".strip()

        user_prompt = f"""
Route this question:

{question}
""".strip()

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.0,
            max_completion_tokens=200,
        )

        content = response.choices[0].message.content

        if not content:
            return QueryRoute(
                query_type=KGQueryType.NONE,
                requested_title=question,
                reason="The router returned an empty response.",
            )

        try:
            data = _extract_json_object(content)

            query_type = KGQueryType(
                data.get("query_type", "none")
            )

            requested_title = data.get("requested_title")

            if requested_title is not None:
                requested_title = str(
                    requested_title
                ).strip() or None

            return QueryRoute(
                query_type=query_type,
                requested_title=requested_title,
                reason=str(
                    data.get("reason", "")
                ).strip(),
            )

        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ):
            # Safe fallback: do not execute a KG query if routing
            # cannot be interpreted.
            return QueryRoute(
                query_type=KGQueryType.NONE,
                requested_title=question,
                reason="Could not parse the routing response.",
            )
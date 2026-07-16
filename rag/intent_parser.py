from __future__ import annotations

import json
import re

from openai import OpenAI

from kg_query.models import PaperQueryIntent


class QueryIntentParser:
    def __init__(
        self,
        client: OpenAI,
        model_name: str,
    ) -> None:
        self.client = client
        self.model_name = model_name

    @staticmethod
    def _extract_json(response_text: str) -> dict:
        response_text = response_text.strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            match = re.search(
                r"\{.*\}",
                response_text,
                flags=re.DOTALL,
            )

            if not match:
                raise ValueError(
                    "The model did not return valid JSON."
                )

            return json.loads(match.group(0))

    def parse(
        self,
        question: str,
    ) -> PaperQueryIntent:
        system_prompt = """
You extract structured search criteria from questions about
academic papers.

Return only one JSON object with these fields:

{
  "title": string or null,
  "author": string or null,
  "category": string or null,
  "year": integer or null,
  "selection": "single", "latest", "oldest", or "most_relevant",
  "requested_information": "abstract"
}

Rules:
- Do not invent missing values.
- Use "latest" when the user asks for the newest or most recent paper.
- Use "oldest" when the user asks for the earliest or oldest paper.
- Use "single" when the user names a particular paper.
- The category should retain identifiers such as cs.AI or cs.LG.
- Return JSON only.
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
                    "content": question,
                },
            ],
            temperature=0.0,
            max_completion_tokens=250,
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "The model returned an empty intent."
            )

        data = self._extract_json(content)

        return PaperQueryIntent(
            title=data.get("title"),
            author=data.get("author"),
            category=data.get("category"),
            year=data.get("year"),
            selection=data.get("selection", "single"),
            requested_information=data.get(
                "requested_information",
                "abstract",
            ),
        )
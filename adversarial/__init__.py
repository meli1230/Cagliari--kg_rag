"""Adversarial tests for the arXiv KG-RAG assistant.

Runs two attacks against the assistant and records what happens:

  1. Indirect prompt injection  - a poisoned "paper" is added to the retrieval
     corpus (in memory only) and the assistant is asked to fetch it. Does the
     model obey the instructions hidden inside the retrieved text?
  2. Jailbreak                  - direct chat prompts that try to break the
     assistant out of its narrow "return a stored abstract" scope.
  3. Piggyback jailbreak        - the same idea, but attached to a request for a
     paper that really is in the corpus, so the attack survives retrieval and
     the generation prompt is actually exercised.

Besides the canary verdict, every case records which stage it reached and whether
the payload was still intact on arrival. An attack stopped by the retrieval gate -
or stripped by the router on the way - never exercised the hardened generation
prompt, so counting it as "defense held" would overstate the result.

Run it:

    python -m adversarial

Both tests call the language model, so they are skipped with a clear message
unless an LLM API key is configured (LLM_API_KEY / OPENAI_API_KEY). A full log,
ready to paste into the README, is written to `adversarial_results.md`.

The package is split into `harness` (paths, canaries, verdicts, setup),
`attacks` (the two tests) and `report` (the Markdown log). Everything a caller
needs is re-exported here, so `import adversarial as adv` is enough.
"""
from __future__ import annotations

from adversarial.harness import (
    CANARY_INJECT,
    CANARY_JAILBREAK,
    RESULTS_PATH,
    RETRIEVAL_MINIMUM_SIMILARITY,
    STAGE_GENERATION,
    STAGE_RETRIEVAL,
    STAGE_UNKNOWN,
    SYSTEM_PROMPT_MARKER,
    CaseResult,
    abstract_is_verbatim,
    answer_body,
    attack_succeeded,
    build_assistant,
    build_retriever,
    classify_stage,
    inject_article,
    looks_like_refusal,
    parse_resolved_title,
    payload_reached_generation,
    verdict_label,
)
from adversarial.attacks import (
    run_injection_attacks,
    run_jailbreak_attacks,
    run_piggyback_attacks,
)
from adversarial.report import main, run_all

__all__ = [
    "CANARY_INJECT",
    "CANARY_JAILBREAK",
    "RESULTS_PATH",
    "RETRIEVAL_MINIMUM_SIMILARITY",
    "STAGE_GENERATION",
    "STAGE_RETRIEVAL",
    "STAGE_UNKNOWN",
    "SYSTEM_PROMPT_MARKER",
    "CaseResult",
    "abstract_is_verbatim",
    "answer_body",
    "attack_succeeded",
    "build_assistant",
    "build_retriever",
    "classify_stage",
    "inject_article",
    "looks_like_refusal",
    "main",
    "parse_resolved_title",
    "payload_reached_generation",
    "run_all",
    "run_injection_attacks",
    "run_jailbreak_attacks",
    "run_piggyback_attacks",
    "verdict_label",
]

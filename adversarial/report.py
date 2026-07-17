"""Run every attack and render the Markdown log written to adversarial_results.md."""
from __future__ import annotations

import io
from datetime import datetime

from adversarial.attacks import (
    run_injection_attacks,
    run_jailbreak_attacks,
    run_piggyback_attacks,
)
from adversarial.harness import (
    RESULTS_PATH,
    STAGE_GENERATION,
    CaseResult,
    build_assistant,
    verdict_label,
)


def _write_case_block(buffer: io.StringIO, case: CaseResult) -> None:
    buffer.write(f"#### {case.name}\n\n")
    buffer.write(
        "- Verdict: **"
        f"{verdict_label(case.attacker_succeeded, case.stage_reached, case.payload_delivered)}"
        f"** ({case.note})\n"
    )
    buffer.write(f"- Stage reached: `{case.stage_reached}`\n")

    if case.payload_delivered is not None:
        buffer.write(
            f"- Payload delivered to the model: "
            f"**{'yes' if case.payload_delivered else 'no'}**\n"
        )

    if case.title_extraction_captured:
        buffer.write(
            "- :warning: Title extraction captured - the resolved title is a chat "
            "reply, not a title\n"
        )

    if case.verbatim_ok is False:
        buffer.write(
            "- :warning: Abstract not verbatim - the model altered the stored text\n"
        )

    buffer.write("\n")
    buffer.write("Input:\n\n```\n")
    buffer.write(case.attack_input.strip() + "\n")
    buffer.write("```\n\n")
    buffer.write("Output:\n\n```\n")
    buffer.write((case.answer or "").strip() + "\n")
    buffer.write("```\n\n")


def _tally(cases: list[CaseResult]) -> tuple[str, str, str]:
    """(got through, reached the model, arrived with the payload intact)."""
    got_through = sum(1 for c in cases if c.attacker_succeeded)
    reached = sum(1 for c in cases if c.stage_reached == STAGE_GENERATION)
    delivered = sum(1 for c in cases if c.payload_delivered)

    return (
        f"{got_through}/{len(cases)} attacks got through",
        f"{reached}/{len(cases)}",
        f"{delivered}/{len(cases)}",
    )


def _write_findings(buffer: io.StringIO, cases: list[CaseResult]) -> None:
    """Narrate what the run actually showed, driven by the recorded diagnostics."""
    buffer.write("## Findings\n\n")

    blocked_early = [c for c in cases if c.stage_reached != STAGE_GENERATION]
    captured = [c for c in cases if c.title_extraction_captured]
    rewritten = [c for c in cases if c.verbatim_ok is False]
    sanitized = [
        c
        for c in cases
        if c.stage_reached == STAGE_GENERATION and c.payload_delivered is False
    ]
    smuggled = [
        c
        for c in cases
        if c.name.startswith("piggyback/") and c.payload_delivered
    ]

    if blocked_early:
        names = ", ".join(f"`{c.name}`" for c in blocked_early)
        buffer.write(
            f"**{len(blocked_early)} of {len(cases)} attacks never reached the generation "
            "model.** The pipeline funnels every question through title extraction and "
            "retrieval first, so a payload that does not look like a stored paper title "
            "dies at the retrieval gate (`rag/pipeline.py`, `minimum_similarity`) and the "
            "hardened system prompt never runs. These cases show that the *architecture* "
            "limits the attack surface - they say nothing about how well the model itself "
            f"resists a payload: {names}.\n\n"
        )

    if captured:
        names = ", ".join(f"`{c.name}`" for c in captured)
        buffer.write(
            f"**The title-extraction step was captured in {len(captured)} case(s)**: "
            f"{names}. Its resolved title is a chat-style refusal rather than a paper "
            "title, which means the attack text did steer that LLM call away from its "
            "task. Unlike `generate_abstract`, the extraction prompt "
            "(`rag/pipeline.py`) carries no untrusted-data rules. The impact is nil here "
            "- the output is only used as a search string, and a refusal simply retrieves "
            "nothing - but the component that stopped the attack was the base model's own "
            "alignment, not this project's design. It is the weakest link in the chain.\n\n"
        )

    if sanitized:
        names = ", ".join(f"`{c.name}`" for c in sanitized)
        buffer.write(
            f"**{len(sanitized)} attack(s) reached the model with the payload already "
            f"stripped**: {names}. Riding on a real paper got them past retrieval, but "
            "the user's question never reaches `generate_abstract` in the first place - "
            "only the extracted `requested_title` does. The router does that extraction "
            "*semantically*, so an instruction bolted onto a title is simply not "
            "carried across, whether it is phrased as a second task or hidden inside "
            "the quotes. This is a real defense and an accidental one: the pipeline "
            "sanitizes by bottleneck, not by refusal. Counting these as 'the model "
            "resisted' would be wrong - it was never asked.\n\n"
        )

    if smuggled:
        names = ", ".join(f"`{c.name}`" for c in smuggled)
        buffer.write(
            f"**The bottleneck is bypassable, and {len(smuggled)} attack(s) did deliver "
            f"the payload into the generation prompt**: {names}. The trick is to stop "
            "fighting the router and lie to it instead: dress the payload as a subtitle "
            "and *assert that it is part of the official title*. The router is told to "
            "preserve an explicitly provided title, its output is never validated "
            "against the corpus, and retrieval still matches because the real title is "
            "a substring of the padded one (the `partial_title` branch even adds a "
            "+0.20 bonus, scoring these ~0.88). The attack text then lands verbatim in "
            "the generation prompt. Together with the corpus-poisoning cases, these are "
            "the only cases in this report that are evidence about the model's own "
            "resistance.\n\n"
        )

    if rewritten:
        names = ", ".join(f"`{c.name}`" for c in rewritten)
        buffer.write(
            f"**Injection resistance came at the cost of fidelity in {len(rewritten)} "
            f"case(s)**: {names}. The model refused the embedded instructions but did not "
            "return the stored abstract verbatim either - it silently dropped the injected "
            "sentence *and* surrounding legitimate text, violating the prompt's own "
            "`do not create, rewrite, summarize, extend or modify the abstract in any way` "
            "rule. Safe, but a real trade-off: a poisoned corpus entry degrades into a "
            "quietly truncated answer with no signal to the user.\n\n"
        )

    if not (blocked_early or captured or rewritten or sanitized):
        buffer.write(
            "Every attack reached the generation model and was refused with the stored "
            "abstract returned verbatim.\n\n"
        )


def run_all() -> str:
    """Run every test that can run, and return a Markdown report as a string."""
    assistant, retriever, status = build_assistant()

    buffer = io.StringIO()
    buffer.write("# Adversarial test results\n\n")
    buffer.write(f"Pipeline status: `{status}`\n\n")
    buffer.write(
        "Generated by `python -m adversarial`. "
        "Both tests require an LLM API key.\n\n"
    )
    buffer.write(f"- Run at: `{datetime.now().isoformat(timespec='seconds')}`\n")
    buffer.write(
        f"- Model: `{assistant.model_name if assistant else 'n/a'}` "
        "(`temperature=0.0`)\n"
    )
    buffer.write(
        "- `Stage reached` records where each attack died: `retrieval` means the "
        "pipeline bailed out before calling the model, so the hardened prompt was "
        "never exercised; `generation` means the model saw the payload and decided.\n\n"
    )

    summary: list[tuple[str, str, str, str]] = []
    all_cases: list[CaseResult] = []

    # --- Tests 1 & 2: only with an LLM. ------------------------------------- #
    if assistant is None:
        print("[Test 1] indirect prompt injection -> SKIPPED (no API key)")
        print("[Test 2] jailbreak                 -> SKIPPED (no API key)")
        print("[Test 3] piggyback jailbreak       -> SKIPPED (no API key)")
        skipped = "_SKIPPED - set `LLM_API_KEY` (or `OPENAI_API_KEY`) and re-run._\n\n"
        buffer.write("## Test 1 - Indirect prompt injection\n\n" + skipped)
        buffer.write("## Test 2 - Jailbreak\n\n" + skipped)
        buffer.write("## Test 3 - Piggyback jailbreak\n\n" + skipped)
        summary.append(("Test 1 - indirect prompt injection", "SKIPPED (no API key)", "-", "-"))
        summary.append(("Test 2 - jailbreak", "SKIPPED (no API key)", "-", "-"))
        summary.append(("Test 3 - piggyback jailbreak", "SKIPPED (no API key)", "-", "-"))
    else:
        print("[Test 1] indirect prompt injection...")
        injection_cases = run_injection_attacks(assistant, retriever)
        buffer.write("## Test 1 - Indirect prompt injection (corpus poisoning)\n\n")
        for case in injection_cases:
            _write_case_block(buffer, case)
        summary.append(("Test 1 - indirect prompt injection", *_tally(injection_cases)))

        print("[Test 2] jailbreak...")
        jailbreak_cases = run_jailbreak_attacks(assistant)
        buffer.write("## Test 2 - Jailbreak (direct chat input)\n\n")
        for case in jailbreak_cases:
            _write_case_block(buffer, case)
        summary.append(("Test 2 - jailbreak", *_tally(jailbreak_cases)))

        print("[Test 3] piggyback jailbreak...")
        piggyback_cases = run_piggyback_attacks(assistant)
        buffer.write("## Test 3 - Piggyback jailbreak (payload attached to a real paper)\n\n")
        buffer.write(
            "Test 2's prompts all died at the retrieval gate, so they never tested the "
            "model. These ride on a paper that really is in the corpus, so the request "
            "survives retrieval and the hardened prompt actually runs.\n\n"
        )
        for case in piggyback_cases:
            _write_case_block(buffer, case)
        summary.append(("Test 3 - piggyback jailbreak", *_tally(piggyback_cases)))

        all_cases = injection_cases + jailbreak_cases + piggyback_cases

    # --- Summary table ------------------------------------------------------ #
    buffer.write("## Summary\n\n")
    buffer.write(
        "| Test | Result | Reached the model | Payload delivered |\n|---|---|---|---|\n"
    )
    for name, result, reached, delivered in summary:
        buffer.write(f"| {name} | {result} | {reached} | {delivered} |\n")
    buffer.write("\n")
    buffer.write(
        "The second column is the headline number; the other two are what make it "
        "meaningful. An attack blocked at retrieval was never a test of the model, and "
        "one that arrived with its payload stripped was not either - only the "
        "right-hand column counts as evidence about the model's own resistance.\n\n"
    )

    if all_cases:
        _write_findings(buffer, all_cases)

    return buffer.getvalue()


def main() -> None:
    report = run_all()
    RESULTS_PATH.write_text(report, encoding="utf-8")

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    # Echo just the summary table lines to the console.
    in_summary = False
    for line in report.splitlines():
        if line.startswith("## Summary"):
            in_summary = True
            continue
        if in_summary and line.strip():
            print(line)

    print(f"\nFull log written to: {RESULTS_PATH}")

from __future__ import annotations

from citation_auditor.models import Claim, Verdict, VerdictLabel


def aggregate_verdicts(claim: Claim, verdicts: list[Verdict]) -> Verdict:
    if not verdicts:
        return Verdict(
            claim=claim,
            label=VerdictLabel.UNKNOWN,
            verifier_name="none",
            authority=0.0,
            rationale="No verifier produced a verdict.",
            evidence=[],
        )

    ranked = sorted(verdicts, key=lambda verdict: verdict.authority, reverse=True)
    highest_authority = ranked[0].authority
    top = [verdict for verdict in ranked if verdict.authority == highest_authority]
    labels = {verdict.label for verdict in top}
    if len(labels) > 1:
        evidence = []
        for verdict in top:
            evidence.extend(verdict.evidence)
        return Verdict(
            claim=claim,
            label=VerdictLabel.UNKNOWN,
            verifier_name="conflict",
            authority=highest_authority,
            rationale="Verifiers with the same authority disagreed, so the claim remains unresolved.",
            evidence=evidence,
        )
    return top[0]


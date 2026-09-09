"""Safety guardrails applied to LLM-written text.

The system prompt tells the model what it must not say. These checks verify it
obeyed, because a prompt is a request, not a constraint. Any violation causes the
LLM output to be discarded in favour of the deterministic recommendation — the
agent would rather be boring than invent a discount that does not exist.

Every pattern here maps to a concrete business or compliance risk:

* fabricated money or percentages → the agent promising offers nobody approved
* guarantee language → implying churn will definitely be prevented
* causal claims → presenting SHAP model evidence as proven cause and effect
* executed actions → claiming an email/credit/change has already happened, when
  the agent has no ability to act at all
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# =========================================================
# 1. DEFINE THE FORBIDDEN PATTERNS
# =========================================================


@dataclass(frozen=True)
class GuardrailRule:
    """One forbidden pattern and the reason it is forbidden.

    Some patterns are only a problem in context. A percentage, for instance, is
    fine when describing SHAP impact ("35% of this customer's total impact") and
    unacceptable when describing an offer ("35% off"). Those rules carry a
    ``context_pattern`` that must also appear nearby for the match to count.
    """

    name: str
    pattern: re.Pattern[str]
    explanation: str
    context_pattern: re.Pattern[str] | None = None
    context_window: int = 60


# Words that turn a number into a commercial offer rather than a statistic.
OFFER_CONTEXT = re.compile(
    r"\b(?:discount\w*|offer\w*|off|credit\w*|rebate\w*|waiv\w*|sav\w*|"
    r"reduc\w*|cheaper|free)\b",
    re.I,
)


GUARDRAIL_RULES: tuple[GuardrailRule, ...] = (
    GuardrailRule(
        name="fabricated_currency_amount",
        pattern=re.compile(r"[$₹€£]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|dollars|rupees|inr|eur|gbp)\b", re.I),
        explanation="quotes a monetary amount that was not supplied by the business",
    ),
    GuardrailRule(
        name="fabricated_percentage_offer",
        pattern=re.compile(r"\b\d{1,3}\s?%|\b\d{1,3}\s?percent\b", re.I),
        explanation="quotes a discount or percentage that was not supplied by the business",
        # Percentages are legitimate when quoting model evidence, so this rule
        # only fires when the number sits next to offer language.
        context_pattern=OFFER_CONTEXT,
    ),
    GuardrailRule(
        name="fabricated_free_offer",
        pattern=re.compile(
            r"\bfree\s+(?:month|months|upgrade|device|service|installation)\b|\bwaive\b", re.I
        ),
        explanation="invents a giveaway or fee waiver that was not supplied by the business",
    ),
    GuardrailRule(
        name="outcome_guarantee",
        pattern=re.compile(
            r"\b(?:guarantee\w*|will\s+(?:prevent|stop|retain|not\s+churn)|ensures?\s+retention"
            r"|definitely\s+(?:stay|retain))\b",
            re.I,
        ),
        explanation="guarantees an outcome the model cannot promise",
    ),
    GuardrailRule(
        name="causal_claim",
        pattern=re.compile(
            r"\b(?:causes?|caused|causing|因)\s+(?:the\s+)?(?:customer\s+)?(?:to\s+)?churn\b"
            r"|\bchurn\s+is\s+caused\s+by\b",
            re.I,
        ),
        explanation="states causation, but SHAP only describes model behaviour",
    ),
    GuardrailRule(
        name="causal_effect_claim",
        pattern=re.compile(
            # "reduce churn", "lowers their churn", "cut churn" — unless the
            # sentence is talking about the model's *estimate*, which is the only
            # thing the what-if simulator actually measures.
            r"\b(?:reduc\w+|lower\w+|cut|cuts|cutting|decreas\w+|drop\w*)\s+"
            r"(?:the\s+|their\s+|his\s+|her\s+|this\s+|customer'?s?\s+)*churn\b"
            r"(?!\s+(?:probabilit\w+|estimate\w*|score\w*|risk\s+estimate))"
            r"|\bchurn\s+reduction\b"
            r"|\bprevent\w*\s+(?:the\s+|this\s+)?(?:customer\s+)?(?:from\s+)?churn",
            re.I,
        ),
        explanation=(
            "claims an intervention changes real churn outcomes, but the simulator only "
            "measures the model's sensitivity to hypothetical feature values"
        ),
    ),
    GuardrailRule(
        name="claimed_executed_action",
        pattern=re.compile(
            r"\b(?:i|we)\s+(?:have\s+)?(?:sent|emailed|applied|credited|updated|contacted|called)\b"
            r"|\b(?:email|sms|discount|credit)\s+(?:has\s+been|was)\s+(?:sent|applied|issued)\b",
            re.I,
        ),
        explanation="claims an action was already carried out, but the agent cannot act",
    ),
)


# =========================================================
# 2. RUN THE CHECKS
# =========================================================


def _has_required_context(text: str, match: re.Match[str], rule: GuardrailRule) -> bool:
    """True when the rule's context word appears near the match."""
    if rule.context_pattern is None:
        return True

    window_start = max(0, match.start() - rule.context_window)
    window_end = match.end() + rule.context_window
    return bool(rule.context_pattern.search(text[window_start:window_end]))


def find_unsupported_claims(*texts: str) -> list[str]:
    """Return a description of every guardrail violation found in ``texts``."""
    violations: list[str] = []

    for text in texts:
        if not text:
            continue
        for rule in GUARDRAIL_RULES:
            # Scan all matches: a sentence may contain a benign percentage and a
            # fabricated one, and only the second should be reported.
            for match in rule.pattern.finditer(text):
                if not _has_required_context(text, match, rule):
                    continue
                violations.append(f"{rule.name}: {rule.explanation} (matched '{match.group(0)}')")
                break

    # Preserve order while removing duplicates across multiple text fragments.
    seen: set[str] = set()
    unique_violations = []
    for violation in violations:
        if violation not in seen:
            seen.add(violation)
            unique_violations.append(violation)
    return unique_violations


def assert_no_unsupported_claims(*texts: str) -> None:
    """Raise ``GuardrailViolation`` when any forbidden pattern is present."""
    violations = find_unsupported_claims(*texts)
    if violations:
        raise GuardrailViolation("; ".join(violations))


class GuardrailViolation(Exception):
    """Raised when LLM output breaks a safety rule and must be discarded."""

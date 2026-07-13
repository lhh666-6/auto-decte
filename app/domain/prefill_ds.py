"""Deterministic field-level decision for recognition candidates."""

from enum import StrEnum
from typing import Any


class PrefillDecision(StrEnum):
    AUTO_PREFILLED = "AUTO_PREFILLED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    RULE_BLOCKED = "RULE_BLOCKED"


def decide_prefill(
    candidate_value: Any,
    confidence: float,
    minimum_confidence: float,
    *,
    type_valid: bool,
    range_valid: bool,
    master_data_valid: bool = True,
    cross_field_valid: bool = True,
) -> PrefillDecision:
    """Classify a candidate without treating it as a confirmed business fact."""
    if candidate_value is None or confidence < minimum_confidence:
        return PrefillDecision.NEEDS_REVIEW
    if not (type_valid and range_valid and master_data_valid and cross_field_valid):
        return PrefillDecision.RULE_BLOCKED
    return PrefillDecision.AUTO_PREFILLED

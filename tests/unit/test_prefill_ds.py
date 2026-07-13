from app.domain.prefill_ds import PrefillDecision, decide_prefill


def test_prefill_requires_value_and_field_threshold() -> None:
    assert (
        decide_prefill(None, 1.0, 0.97, type_valid=True, range_valid=True)
        is PrefillDecision.NEEDS_REVIEW
    )
    assert (
        decide_prefill("8", 0.96, 0.97, type_valid=True, range_valid=True)
        is PrefillDecision.NEEDS_REVIEW
    )


def test_prefill_blocks_invalid_rules_before_auto_prefill() -> None:
    assert (
        decide_prefill("8", 0.99, 0.97, type_valid=True, range_valid=False)
        is PrefillDecision.RULE_BLOCKED
    )
    assert (
        decide_prefill("8", 0.99, 0.97, type_valid=True, range_valid=True)
        is PrefillDecision.AUTO_PREFILLED
    )

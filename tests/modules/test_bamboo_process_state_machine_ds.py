from app.modules.bamboo_process.models_ds import BambooRole, BambooStage, StageSubmission
from app.modules.bamboo_process.state_machine_ds import (
    can_submit_stage,
    next_stage,
    visible_to_role,
)


def test_new_record_starts_at_sort() -> None:
    assert next_stage([]) is BambooStage.SORT


def test_signed_stages_open_the_next_main_stage() -> None:
    submissions = [_submission(BambooStage.SORT)]
    assert next_stage(submissions) is BambooStage.DIPPING

    submissions.append(_submission(BambooStage.DIPPING))
    assert next_stage(submissions) is BambooStage.DRYING

    submissions.append(_submission(BambooStage.DRYING))
    assert next_stage(submissions) is BambooStage.SUPERVISOR

    submissions.append(_submission(BambooStage.SUPERVISOR))
    assert next_stage(submissions) is BambooStage.PLANT_AUDIT

    submissions.append(_submission(BambooStage.PLANT_AUDIT))
    assert next_stage(submissions) is None


def test_invalidated_submission_reopens_its_stage() -> None:
    submissions = [
        _submission(BambooStage.SORT),
        _submission(BambooStage.DIPPING, invalidated=True),
        _submission(BambooStage.DRYING, invalidated=True),
    ]

    assert next_stage(submissions) is BambooStage.DIPPING


def test_downstream_operator_is_hidden_until_the_previous_signature() -> None:
    assert visible_to_role([], BambooRole.SORT_OPERATOR)
    assert not visible_to_role([], BambooRole.DIPPING_OPERATOR)

    after_sort = [_submission(BambooStage.SORT)]
    assert visible_to_role(after_sort, BambooRole.DIPPING_OPERATOR)
    assert not visible_to_role(after_sort, BambooRole.DRYING_RACK_OPERATOR)

    after_dipping = [*after_sort, _submission(BambooStage.DIPPING)]
    assert visible_to_role(after_dipping, BambooRole.DRYING_RACK_OPERATOR)
    assert not visible_to_role(after_dipping, BambooRole.SUPERVISOR)


def test_supervision_and_finance_visibility_open_by_layer() -> None:
    production_complete = [
        _submission(BambooStage.SORT),
        _submission(BambooStage.DIPPING),
        _submission(BambooStage.DRYING),
    ]
    assert visible_to_role(production_complete, BambooRole.SUPERVISOR)
    assert visible_to_role(production_complete, BambooRole.INSPECTOR)
    assert not visible_to_role(production_complete, BambooRole.PLANT_MANAGER)
    assert not visible_to_role(production_complete, BambooRole.FINANCE_APPROVER)

    supervisor_complete = [
        *production_complete,
        _submission(BambooStage.SUPERVISOR),
    ]
    assert visible_to_role(supervisor_complete, BambooRole.INSPECTOR)
    assert visible_to_role(supervisor_complete, BambooRole.PLANT_MANAGER)

    audited = [
        *supervisor_complete,
        _submission(BambooStage.PLANT_AUDIT),
    ]
    assert visible_to_role(audited, BambooRole.FINANCE_APPROVER)
    assert visible_to_role(audited, BambooRole.SYSTEM_ADMIN)


def test_signer_keeps_read_only_visibility_after_completing_a_stage() -> None:
    after_sort = [_submission(BambooStage.SORT)]

    assert visible_to_role(after_sort, BambooRole.SORT_OPERATOR)
    assert visible_to_role(after_sort, BambooRole.DIPPING_OPERATOR)


def test_each_main_stage_requires_its_assigned_role() -> None:
    assert can_submit_stage(BambooRole.SORT_OPERATOR, BambooStage.SORT)
    assert can_submit_stage(BambooRole.DIPPING_OPERATOR, BambooStage.DIPPING)
    assert can_submit_stage(BambooRole.DRYING_RACK_OPERATOR, BambooStage.DRYING)
    assert can_submit_stage(BambooRole.SUPERVISOR, BambooStage.SUPERVISOR)
    assert can_submit_stage(BambooRole.PLANT_MANAGER, BambooStage.PLANT_AUDIT)
    assert not can_submit_stage(BambooRole.INSPECTOR, BambooStage.SUPERVISOR)
    assert not can_submit_stage(BambooRole.SORT_OPERATOR, BambooStage.DIPPING)


def _submission(stage: BambooStage, *, invalidated: bool = False) -> StageSubmission:
    return StageSubmission(
        submission_id=f"SUB-{stage.value}",
        record_id="BR-1",
        stage=stage,
        version=1,
        values={},
        actor_id="E-1",
        actor_name="测试员工",
        role_code="TEST_ROLE",
        factory_id="FACTORY-A",
        submitted_at="2026-07-22T10:00:00+08:00",
        invalidated=invalidated,
    )

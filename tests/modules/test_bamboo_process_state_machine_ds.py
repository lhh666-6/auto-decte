from app.modules.bamboo_process.models_ds import (
    BambooFormType,
    BambooRole,
    BambooStage,
    StageSubmission,
)
from app.modules.bamboo_process.state_machine_ds import (
    can_submit_stage,
    next_stage,
    visible_to_role,
)


def test_sorting_form_advances_only_through_its_approval_chain() -> None:
    submissions: list[StageSubmission] = []
    assert next_stage(submissions, BambooFormType.SORTING) is BambooStage.SORT

    submissions.append(_submission(BambooStage.SORT))
    assert next_stage(submissions, BambooFormType.SORTING) is BambooStage.SUPERVISOR

    submissions.append(_submission(BambooStage.SUPERVISOR))
    assert next_stage(submissions, BambooFormType.SORTING) is BambooStage.PLANT_AUDIT

    submissions.append(_submission(BambooStage.PLANT_AUDIT))
    assert next_stage(submissions, BambooFormType.SORTING) is None


def test_dipping_drying_form_advances_through_both_production_stages() -> None:
    submissions: list[StageSubmission] = []
    form_type = BambooFormType.DIPPING_DRYING
    assert next_stage(submissions, form_type) is BambooStage.DIPPING

    submissions.append(_submission(BambooStage.DIPPING))
    assert next_stage(submissions, form_type) is BambooStage.DRYING

    submissions.append(_submission(BambooStage.DRYING))
    assert next_stage(submissions, form_type) is BambooStage.SUPERVISOR

    submissions.append(_submission(BambooStage.SUPERVISOR))
    assert next_stage(submissions, form_type) is BambooStage.PLANT_AUDIT

    submissions.append(_submission(BambooStage.PLANT_AUDIT))
    assert next_stage(submissions, form_type) is None


def test_invalidated_submission_reopens_the_stage_on_its_own_form() -> None:
    submissions = [
        _submission(BambooStage.DIPPING),
        _submission(BambooStage.DRYING, invalidated=True),
    ]

    assert (
        next_stage(submissions, BambooFormType.DIPPING_DRYING)
        is BambooStage.DRYING
    )


def test_visibility_is_scoped_to_the_independent_form_stage_order() -> None:
    after_sort = [_submission(BambooStage.SORT)]
    assert visible_to_role(after_sort, BambooRole.SORT_OPERATOR, BambooFormType.SORTING)
    assert visible_to_role(after_sort, BambooRole.SUPERVISOR, BambooFormType.SORTING)
    assert not visible_to_role(
        after_sort,
        BambooRole.DIPPING_OPERATOR,
        BambooFormType.SORTING,
    )

    after_dipping = [_submission(BambooStage.DIPPING)]
    assert visible_to_role(
        after_dipping,
        BambooRole.DIPPING_OPERATOR,
        BambooFormType.DIPPING_DRYING,
    )
    assert visible_to_role(
        after_dipping,
        BambooRole.DRYING_RACK_OPERATOR,
        BambooFormType.DIPPING_DRYING,
    )
    assert not visible_to_role(
        after_dipping,
        BambooRole.SUPERVISOR,
        BambooFormType.DIPPING_DRYING,
    )


def test_supervision_and_finance_visibility_open_by_layer() -> None:
    form_type = BambooFormType.DIPPING_DRYING
    production_complete = [
        _submission(BambooStage.DIPPING),
        _submission(BambooStage.DRYING),
    ]
    assert visible_to_role(production_complete, BambooRole.SUPERVISOR, form_type)
    assert visible_to_role(production_complete, BambooRole.INSPECTOR, form_type)
    assert not visible_to_role(production_complete, BambooRole.PLANT_MANAGER, form_type)
    assert not visible_to_role(production_complete, BambooRole.FINANCE_APPROVER, form_type)

    supervisor_complete = [
        *production_complete,
        _submission(BambooStage.SUPERVISOR),
    ]
    assert visible_to_role(supervisor_complete, BambooRole.PLANT_MANAGER, form_type)

    audited = [
        *supervisor_complete,
        _submission(BambooStage.PLANT_AUDIT),
    ]
    assert visible_to_role(audited, BambooRole.FINANCE_APPROVER, form_type)
    assert visible_to_role(audited, BambooRole.SYSTEM_ADMIN, form_type)


def test_stage_permissions_reject_stages_from_the_other_form() -> None:
    assert can_submit_stage(
        BambooRole.SORT_OPERATOR,
        BambooStage.SORT,
        BambooFormType.SORTING,
    )
    assert can_submit_stage(
        BambooRole.DIPPING_OPERATOR,
        BambooStage.DIPPING,
        BambooFormType.DIPPING_DRYING,
    )
    assert can_submit_stage(
        BambooRole.DRYING_RACK_OPERATOR,
        BambooStage.DRYING,
        BambooFormType.DIPPING_DRYING,
    )
    assert not can_submit_stage(
        BambooRole.DIPPING_OPERATOR,
        BambooStage.DIPPING,
        BambooFormType.SORTING,
    )
    assert not can_submit_stage(
        BambooRole.SORT_OPERATOR,
        BambooStage.SORT,
        BambooFormType.DIPPING_DRYING,
    )


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
        submitted_at="2026-07-22T10:00:00+08:00",  # type: ignore[arg-type]
        invalidated=invalidated,
    )

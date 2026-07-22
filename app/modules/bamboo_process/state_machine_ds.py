"""Pure stage progression rules for bamboo production records."""

from collections.abc import Sequence

from app.modules.bamboo_process.models_ds import (
    BambooRole,
    BambooStage,
    StageSubmission,
)

MAIN_STAGE_ORDER = (
    BambooStage.SORT,
    BambooStage.DIPPING,
    BambooStage.DRYING,
    BambooStage.SUPERVISOR,
    BambooStage.PLANT_AUDIT,
)

STAGE_ROLE = {
    BambooStage.SORT: BambooRole.SORT_OPERATOR,
    BambooStage.DIPPING: BambooRole.DIPPING_OPERATOR,
    BambooStage.DRYING: BambooRole.DRYING_RACK_OPERATOR,
    BambooStage.SUPERVISOR: BambooRole.SUPERVISOR,
    BambooStage.PLANT_AUDIT: BambooRole.PLANT_MANAGER,
}


def can_submit_stage(role: BambooRole, stage: BambooStage) -> bool:
    return STAGE_ROLE[stage] is role


def next_stage(submissions: Sequence[StageSubmission]) -> BambooStage | None:
    signed_stages = {
        submission.stage for submission in submissions if not submission.invalidated
    }
    return next((stage for stage in MAIN_STAGE_ORDER if stage not in signed_stages), None)


def visible_to_role(
    submissions: Sequence[StageSubmission],
    role: BambooRole,
) -> bool:
    signed_stages = {
        submission.stage for submission in submissions if not submission.invalidated
    }
    if role is BambooRole.SYSTEM_ADMIN:
        return True
    if role is BambooRole.INSPECTOR:
        return BambooStage.DRYING in signed_stages
    if role is BambooRole.FINANCE_APPROVER:
        return BambooStage.PLANT_AUDIT in signed_stages
    completed_stage = next(
        (stage for stage, assigned_role in STAGE_ROLE.items() if assigned_role is role),
        None,
    )
    if completed_stage in signed_stages:
        return True
    current_stage = next_stage(submissions)
    return current_stage is not None and STAGE_ROLE[current_stage] is role

from datetime import date

from fastapi import APIRouter

from app.dates import current_date
from app.dependencies import DatabaseSession, EmployeeScope
from app.schemas import AssignmentSummaryRead
from app.services.impact_summaries import build_assignment_summary

router = APIRouter(tags=["impact summaries"])


@router.get("/assignment-summary", response_model=AssignmentSummaryRead)
def assignment_summary(
    session: DatabaseSession,
    visibility: EmployeeScope,
    evaluation_date: date | None = None,
) -> AssignmentSummaryRead:
    return build_assignment_summary(
        session,
        evaluation_date or current_date(),
        visible_employee_ids=(
            None if visibility.unrestricted else set(visibility.employee_ids)
        ),
    )

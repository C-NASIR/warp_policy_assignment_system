from fastapi import APIRouter, HTTPException

from app.dependencies import AssignmentFieldScope, DatabaseSession, EmployeeScope
from app.schemas import AssignmentQueryCreate, EmployeeAssignmentQueryRead
from app.services.assignment_queries import (
    AssignmentQueryEmployeeNotFoundError,
    EmployeeAssignmentQueryResult,
    query_employee_assignments,
)
from app.services.employee_visibility import visible_employee_or_404

router = APIRouter(prefix="/assignment-queries", tags=["assignment queries"])


@router.post("", response_model=list[EmployeeAssignmentQueryRead])
def query(
    data: AssignmentQueryCreate,
    session: DatabaseSession,
    visibility: EmployeeScope,
    field_visibility: AssignmentFieldScope,
) -> list[EmployeeAssignmentQueryResult]:
    for employee_id in set(data.employee_ids):
        visible_employee_or_404(session, visibility, employee_id)
    try:
        return query_employee_assignments(
            session,
            data.employee_ids,
            data.evaluation_date,
            visible_assignment_field_ids=(
                None
                if field_visibility.unrestricted
                else set(field_visibility.assignment_field_ids)
            ),
        )
    except AssignmentQueryEmployeeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

from fastapi import APIRouter, HTTPException

from app.dependencies import DatabaseSession
from app.schemas import AssignmentQueryCreate, EmployeeAssignmentQueryRead
from app.services.assignment_queries import (
    AssignmentQueryEmployeeNotFoundError,
    EmployeeAssignmentQueryResult,
    query_employee_assignments,
)

router = APIRouter(prefix="/assignment-queries", tags=["assignment queries"])


@router.post("", response_model=list[EmployeeAssignmentQueryRead])
def query(
    data: AssignmentQueryCreate,
    session: DatabaseSession,
) -> list[EmployeeAssignmentQueryResult]:
    try:
        return query_employee_assignments(
            session,
            data.employee_ids,
            data.evaluation_date,
        )
    except AssignmentQueryEmployeeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import create_tables
from app.error_contract import (
    conflict_response,
    error_response,
    validation_issue,
    validation_response,
)
from app.routers import (
    assignment_fields,
    assignment_queries,
    audit_logs,
    change_previews,
    condition_fields,
    employees,
    groups,
    policies,
)
from app.schemas import APIErrorResponseRead
from app.services.change_approvals import (
    ChangeApprovalConflictError,
    ChangeApprovalValidationError,
)
from app.services.employee_overrides import (
    EmployeeOverrideConflictError,
    EmployeeOverrideResourceNotFoundError,
)
from app.services.groups import GroupResourceNotFoundError
from app.services.org_chart import (
    EmployeeHierarchyConflictError,
    EmployeeManagerNotFoundError,
)
from app.services.policy_engine import PolicyConflictError
from app.services.policy_versions import (
    EffectivePolicyVersionConflictError,
    PolicyVersionOverlapError,
)
from app.services.reconciliation import AssignmentReconciliationOrderError


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Policy Assignment System",
    version="1.0.0",
    lifespan=lifespan,
    responses={
        409: {
            "model": APIErrorResponseRead,
            "description": "A deterministic domain conflict prevented the change",
        },
        422: {
            "model": APIErrorResponseRead,
            "description": "The request failed structural or domain validation",
        },
    },
)
app.include_router(employees.router)
app.include_router(assignment_queries.router)
app.include_router(assignment_fields.router)
app.include_router(condition_fields.router)
app.include_router(policies.router)
app.include_router(groups.router)
app.include_router(audit_logs.router)
app.include_router(change_previews.router)
app.include_router(change_previews.execution_router)


@app.exception_handler(PolicyConflictError)
async def policy_conflict_handler(_: Request, exc: PolicyConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(GroupResourceNotFoundError)
async def group_resource_not_found_handler(
    _: Request,
    exc: GroupResourceNotFoundError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(EmployeeManagerNotFoundError)
async def employee_manager_not_found_handler(
    _: Request,
    exc: EmployeeManagerNotFoundError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(EmployeeHierarchyConflictError)
async def employee_hierarchy_conflict_handler(
    _: Request,
    exc: EmployeeHierarchyConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(EmployeeOverrideResourceNotFoundError)
async def employee_override_not_found_handler(
    _: Request,
    exc: EmployeeOverrideResourceNotFoundError,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(EmployeeOverrideConflictError)
async def employee_override_conflict_handler(
    _: Request,
    exc: EmployeeOverrideConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(PolicyVersionOverlapError)
@app.exception_handler(EffectivePolicyVersionConflictError)
async def policy_version_conflict_handler(
    _: Request,
    exc: PolicyVersionOverlapError | EffectivePolicyVersionConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(AssignmentReconciliationOrderError)
async def assignment_reconciliation_order_handler(
    _: Request,
    exc: AssignmentReconciliationOrderError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(ChangeApprovalConflictError)
async def change_approval_conflict_handler(
    _: Request,
    exc: ChangeApprovalConflictError,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=error_response(
            category="conflict",
            code=exc.code,
            message=str(exc),
            issues=[
                validation_issue(
                    code=exc.code,
                    message=str(exc),
                    path=["change_approval"],
                    metadata=exc.metadata,
                )
            ],
            legacy_detail=str(exc),
        ),
    )


@app.exception_handler(ChangeApprovalValidationError)
async def change_approval_validation_handler(
    _: Request,
    exc: ChangeApprovalValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_response(
            category="validation",
            code=exc.code,
            message=str(exc),
            issues=[
                validation_issue(
                    code=exc.code,
                    message=str(exc),
                    path=["approval_token"],
                    metadata=exc.metadata,
                )
            ],
            legacy_detail=str(exc),
        ),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    raw_errors = exc.errors()
    issues = [
        validation_issue(
            code=error["type"],
            message=error["msg"],
            path=[
                item if isinstance(item, (str, int)) else str(item)
                for item in error.get("loc", ())
            ],
            metadata=error.get("ctx"),
        )
        for error in raw_errors
    ]
    return JSONResponse(
        status_code=422,
        content=validation_response(
            issues=issues,
            legacy_detail=jsonable_encoder(raw_errors),
        ),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 409:
        message = _http_error_message(exc.detail)
        content = error_response(
            category="conflict",
            code="conflict",
            message=message,
            issues=[validation_issue(code="conflict", message=message)],
            legacy_detail=exc.detail,
        )
    elif exc.status_code == 422:
        message = _http_error_message(exc.detail)
        content = validation_response(
            issues=[validation_issue(code="invalid_request", message=message)],
            legacy_detail=exc.detail,
        )
    else:
        content = {"detail": jsonable_encoder(exc.detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=exc.headers,
    )


def _http_error_message(detail) -> str:
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    if isinstance(detail, str):
        return detail
    return "Request could not be processed"


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "policy-assignment-system"}

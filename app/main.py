from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.database import create_tables
from app.routers import (
    assignment_fields,
    audit_logs,
    condition_fields,
    employees,
    groups,
    policies,
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


app = FastAPI(title="Policy Assignment System", version="1.0.0", lifespan=lifespan)
app.include_router(employees.router)
app.include_router(assignment_fields.router)
app.include_router(condition_fields.router)
app.include_router(policies.router)
app.include_router(groups.router)
app.include_router(audit_logs.router)


@app.exception_handler(PolicyConflictError)
async def policy_conflict_handler(_: Request, exc: PolicyConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


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
    return JSONResponse(status_code=409, content={"detail": str(exc)})


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
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(PolicyVersionOverlapError)
@app.exception_handler(EffectivePolicyVersionConflictError)
async def policy_version_conflict_handler(
    _: Request,
    exc: PolicyVersionOverlapError | EffectivePolicyVersionConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(AssignmentReconciliationOrderError)
async def assignment_reconciliation_order_handler(
    _: Request,
    exc: AssignmentReconciliationOrderError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "policy-assignment-system"}

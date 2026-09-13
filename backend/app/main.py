from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.browser_access import configure_browser_access
from app.database import create_tables
from app.dependencies import DatabaseSession, authorize_operation
from app.error_contract import (
    conflict_response,
    error_response,
    validation_issue,
    validation_response,
)
from app.routers import (
    access_control,
    approval_requests,
    assignment_fields,
    assignment_queries,
    audit_logs,
    auth,
    change_previews,
    condition_fields,
    employees,
    groups,
    human_auth,
    impact_summaries,
    policies,
)
from app.schemas import APIErrorResponseRead
from app.services.access_control import PermissionDeniedError, required_permissions
from app.services.assignment_values import AssignmentValueError
from app.services.auth import (
    AuthenticationError,
    AuthorizationError,
    CredentialConflictError,
    CredentialValidationError,
    required_scope,
)
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

HUMAN_AUTH_PATHS = {
    "/auth/setup-status",
    "/auth/setup-root",
    "/auth/login",
    "/auth/me",
    "/auth/logout",
    "/auth/change-password",
    "/auth/password-reset/request",
    "/auth/password-reset/confirm",
    "/auth/security",
    "/auth/mfa/setup",
    "/auth/mfa/confirm",
    "/auth/mfa",
    "/auth/reauthenticate",
    "/auth/sessions/revoke-others",
    "/auth/sessions/revoke-all",
    "/auth/security-events/{event_id}/acknowledge",
}


class PolicyAssignmentAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        """Publish the exact operation scope alongside bearer authentication."""
        if self.openapi_schema is not None:
            return self.openapi_schema
        schema = get_openapi(
            title=self.title,
            version=self.version,
            description=self.description,
            routes=self.routes,
        )
        for path, path_item in schema.get("paths", {}).items():
            if path == "/" or path in HUMAN_AUTH_PATHS:
                continue
            for method, operation in path_item.items():
                if method.upper() not in {
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "OPTIONS",
                    "HEAD",
                }:
                    continue
                operation["x-required-scopes"] = [required_scope(method, path)]
                operation["x-required-permissions"] = sorted(
                    required_permissions(method, path)
                )
                success_response = operation.get("responses", {}).get("200", {})
                response_schema = (
                    success_response.get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                )
                query_parameter_names = {
                    parameter.get("name")
                    for parameter in operation.get("parameters", [])
                    if parameter.get("in") == "query"
                }
                if (
                    response_schema.get("type") == "array"
                    and {
                        "limit",
                        "offset",
                    }
                    <= query_parameter_names
                ):
                    success_response.setdefault("headers", {}).update(
                        {
                            "X-Total-Count": {
                                "description": "Total items matching the filters",
                                "schema": {"type": "integer", "minimum": 0},
                            },
                            "X-Limit": {
                                "description": "Maximum items requested",
                                "schema": {"type": "integer", "minimum": 1},
                            },
                            "X-Offset": {
                                "description": "Matching items skipped",
                                "schema": {"type": "integer", "minimum": 0},
                            },
                        }
                    )
        self.openapi_schema = schema
        return schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = PolicyAssignmentAPI(
    title="Policy Assignment System",
    version="1.0.0",
    lifespan=lifespan,
    responses={
        401: {
            "model": APIErrorResponseRead,
            "description": "A valid API credential or user session is required",
        },
        403: {
            "model": APIErrorResponseRead,
            "description": "The credential scope or human role lacks the required access",
        },
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
configure_browser_access(app)
app.include_router(human_auth.public_router)
app.include_router(human_auth.session_router)
for protected_router in (
    employees.router,
    assignment_queries.router,
    assignment_fields.router,
    condition_fields.router,
    policies.router,
    groups.router,
    impact_summaries.router,
    audit_logs.router,
    change_previews.router,
    change_previews.execution_router,
    auth.router,
    access_control.authorization_router,
    access_control.roles_router,
    access_control.users_router,
    approval_requests.router,
):
    app.include_router(
        protected_router,
        dependencies=[Depends(authorize_operation)],
    )


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(
    _: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    response_status = (
        429
        if exc.code == "login_throttled"
        else 403
        if exc.code == "mfa_enrollment_required"
        else 401
    )
    headers = {"WWW-Authenticate": "Bearer"}
    if exc.code == "login_throttled" and exc.metadata.get("retry_after_seconds"):
        headers["Retry-After"] = str(exc.metadata["retry_after_seconds"])
    return JSONResponse(
        status_code=response_status,
        content=error_response(
            category="authentication",
            code=exc.code,
            message=str(exc),
            issues=[
                validation_issue(
                    code=exc.code,
                    message=str(exc),
                    path=["authorization"],
                    metadata=exc.metadata,
                )
            ],
        ),
        headers=headers,
    )


@app.exception_handler(AuthorizationError)
async def authorization_error_handler(
    _: Request,
    exc: AuthorizationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_response(
            category="authorization",
            code=exc.code,
            message=str(exc),
            issues=[
                validation_issue(
                    code=exc.code,
                    message=str(exc),
                    path=["authorization", "scopes"],
                    metadata=exc.metadata,
                )
            ],
        ),
    )


@app.exception_handler(PermissionDeniedError)
async def permission_denied_error_handler(
    _: Request,
    exc: PermissionDeniedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=error_response(
            category="authorization",
            code=exc.code,
            message=str(exc),
            issues=[
                validation_issue(
                    code=exc.code,
                    message=str(exc),
                    path=["authorization", "permissions"],
                    metadata=exc.metadata,
                )
            ],
        ),
    )


@app.exception_handler(CredentialConflictError)
async def credential_conflict_handler(
    _: Request,
    exc: CredentialConflictError,
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
                    path=["auth", "credentials", "name"],
                    metadata=exc.metadata,
                )
            ],
        ),
    )


@app.exception_handler(CredentialValidationError)
async def credential_validation_handler(
    _: Request,
    exc: CredentialValidationError,
) -> JSONResponse:
    path: list[str | int] = ["body", "scopes"]
    if exc.code == "credential_expiry_not_future":
        path = ["body", "expires_at"]
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
                    path=path,
                    metadata=exc.metadata,
                )
            ],
        ),
    )


@app.exception_handler(PolicyConflictError)
async def policy_conflict_handler(_: Request, exc: PolicyConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(GroupResourceNotFoundError)
async def group_resource_not_found_handler(
    _: Request,
    exc: GroupResourceNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_response(
            category="not_found",
            code="resource_not_found",
            message=str(exc),
            issues=[validation_issue(code="resource_not_found", message=str(exc))],
        ),
    )


@app.exception_handler(EmployeeManagerNotFoundError)
async def employee_manager_not_found_handler(
    _: Request,
    exc: EmployeeManagerNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_response(
            category="not_found",
            code="resource_not_found",
            message=str(exc),
            issues=[validation_issue(code="resource_not_found", message=str(exc))],
        ),
    )


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
    return JSONResponse(
        status_code=404,
        content=error_response(
            category="not_found",
            code="resource_not_found",
            message=str(exc),
            issues=[validation_issue(code="resource_not_found", message=str(exc))],
        ),
    )


@app.exception_handler(EmployeeOverrideConflictError)
async def employee_override_conflict_handler(
    _: Request,
    exc: EmployeeOverrideConflictError,
) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict_response(exc))


@app.exception_handler(AssignmentValueError)
async def assignment_value_error_handler(
    _: Request,
    exc: AssignmentValueError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=validation_response(
            issues=[
                validation_issue(
                    code="invalid_assignment_value",
                    message=str(exc),
                    path=["body", "value"],
                    metadata=exc.metadata,
                )
            ],
        ),
    )


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
        )
    elif exc.status_code == 422:
        message = _http_error_message(exc.detail)
        content = validation_response(
            issues=[validation_issue(code="invalid_request", message=message)],
        )
    else:
        message = _http_error_message(exc.detail)
        category = (
            "authentication"
            if exc.status_code == 401
            else "authorization"
            if exc.status_code == 403
            else "not_found"
            if exc.status_code == 404
            else "service"
            if exc.status_code >= 500
            else "validation"
        )
        code = (
            "authentication_failed"
            if exc.status_code == 401
            else "forbidden"
            if exc.status_code == 403
            else "resource_not_found"
            if exc.status_code == 404
            else "service_unavailable"
            if exc.status_code >= 500
            else "invalid_request"
        )
        content = error_response(
            category=category,
            code=code,
            message=message,
            issues=[validation_issue(code=code, message=message)],
        )
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
def health(session: DatabaseSession) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": "policy-assignment-system",
        "database": "ready",
    }

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.dependencies import DatabaseSession, HumanSession
from app.models import AutomatedUserRole, Role
from app.schemas import (
    HumanLoginCreate,
    PasswordChangeCreate,
    RoleSummaryRead,
    RootSetupCreate,
    RootSetupStatusRead,
    UserRead,
)
from app.services.access_control import effective_permissions
from app.services.human_auth import (
    SESSION_COOKIE_NAME,
    authenticate_human,
    change_password,
    create_root_user,
    revoke_session,
    root_setup_required,
    session_cookie_secure,
    session_ttl_seconds,
)

public_router = APIRouter(prefix="/auth", tags=["human authentication"])
session_router = APIRouter(prefix="/auth", tags=["human authentication"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=session_ttl_seconds(),
        path="/",
        secure=session_cookie_secure(),
        httponly=True,
        samesite="strict",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=session_cookie_secure(),
        httponly=True,
        samesite="strict",
    )


def _user_read(session: DatabaseSession, user) -> UserRead:
    automated_roles = list(
        session.scalars(
            select(Role)
            .join(AutomatedUserRole, AutomatedUserRole.role_id == Role.id)
            .where(AutomatedUserRole.user_id == user.id)
            .distinct()
            .order_by(Role.name)
        )
    )
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_root=user.is_root,
        password_change_required=user.password_change_required,
        employee_id=user.employee_id,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=[RoleSummaryRead.model_validate(role) for role in sorted(user.roles, key=lambda item: item.name)],
        automated_roles=[
            RoleSummaryRead.model_validate(role) for role in automated_roles
        ],
        permissions=sorted(effective_permissions(session, user)),
    )


@public_router.get("/setup-status", response_model=RootSetupStatusRead)
def setup_status(session: DatabaseSession) -> RootSetupStatusRead:
    return RootSetupStatusRead(setup_required=root_setup_required(session))


@public_router.post(
    "/setup-root",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def setup_root(
    data: RootSetupCreate,
    response: Response,
    session: DatabaseSession,
) -> UserRead:
    try:
        user, created_session = create_root_user(
            session,
            name=data.name,
            email=str(data.email),
            password=data.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _set_session_cookie(response, created_session.token)
    return _user_read(session, user)


@public_router.post("/login", response_model=UserRead)
def login(
    data: HumanLoginCreate,
    response: Response,
    session: DatabaseSession,
) -> UserRead:
    user, created_session = authenticate_human(
        session,
        email=str(data.email),
        password=data.password,
    )
    _set_session_cookie(response, created_session.token)
    return _user_read(session, user)


@session_router.get("/me", response_model=UserRead)
def me(identity: HumanSession, session: DatabaseSession) -> UserRead:
    return _user_read(session, identity.user)


@session_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: DatabaseSession,
    identity: HumanSession,
) -> None:
    revoke_session(session, identity.session)
    _clear_session_cookie(response)


@session_router.post("/change-password", response_model=UserRead)
def update_password(
    data: PasswordChangeCreate,
    response: Response,
    session: DatabaseSession,
    identity: HumanSession,
) -> UserRead:
    try:
        replacement = change_password(
            session,
            user=identity.user,
            current_session=identity.session,
            current_password=data.current_password,
            new_password=data.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    _set_session_cookie(response, replacement.token)
    return _user_read(session, identity.user)

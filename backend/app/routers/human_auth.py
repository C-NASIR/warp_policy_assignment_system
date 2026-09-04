from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.dependencies import DatabaseSession, HumanSession
from app.models import AuthSession, AutomatedUserRole, Role, SecurityEvent
from app.schemas import (
    AccountSecurityRead,
    AuthSessionRead,
    HumanLoginCreate,
    MFAConfirmCreate,
    MFAConfirmRead,
    MFADisableCreate,
    MFASetupCreate,
    MFASetupRead,
    PasswordChangeCreate,
    PasswordResetConfirmCreate,
    PasswordResetRequestCreate,
    PasswordResetRequestRead,
    ReauthenticateCreate,
    RoleSummaryRead,
    RootSetupCreate,
    RootSetupStatusRead,
    SecurityEventRead,
    UserRead,
)
from app.services.access_control import effective_permissions
from app.services.auth import AuthenticationError
from app.services.human_auth import (
    SESSION_COOKIE_NAME,
    acknowledge_security_event,
    authenticate_human,
    begin_mfa_setup,
    change_password,
    confirm_mfa_setup,
    confirm_password_reset,
    create_root_user,
    disable_mfa,
    password_reset_token_exposed,
    privileged_mfa_required,
    reauthenticate,
    request_password_reset,
    revoke_session,
    revoke_user_sessions,
    root_setup_required,
    session_cookie_secure,
    session_recently_reauthenticated,
    session_ttl_seconds,
)

public_router = APIRouter(prefix="/auth", tags=["human authentication"])
session_router = APIRouter(prefix="/auth", tags=["human authentication"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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
        mfa_enabled=user.mfa_enabled,
        employee_id=user.employee_id,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        roles=[
            RoleSummaryRead.model_validate(role)
            for role in sorted(user.roles, key=lambda item: item.name)
        ],
        automated_roles=[
            RoleSummaryRead.model_validate(role) for role in automated_roles
        ],
        permissions=sorted(effective_permissions(session, user)),
    )


@public_router.get("/setup-status", response_model=RootSetupStatusRead)
def setup_status(session: DatabaseSession) -> RootSetupStatusRead:
    return RootSetupStatusRead(setup_required=root_setup_required(session))


@public_router.post(
    "/setup-root", response_model=UserRead, status_code=status.HTTP_201_CREATED
)
def setup_root(
    data: RootSetupCreate,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> UserRead:
    try:
        user, created_session = create_root_user(
            session,
            name=data.name,
            email=str(data.email),
            password=data.password,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _set_session_cookie(response, created_session.token)
    return _user_read(session, user)


@public_router.post("/login", response_model=UserRead)
def login(
    data: HumanLoginCreate,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> UserRead:
    try:
        user, created_session = authenticate_human(
            session,
            email=str(data.email),
            password=data.password,
            mfa_code=data.mfa_code,
            recovery_code=data.recovery_code,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError:
        # Throttle counters and failed-login alerts must survive the rejected request.
        session.commit()
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    _set_session_cookie(response, created_session.token)
    return _user_read(session, user)


@public_router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_password_reset(
    data: PasswordResetRequestCreate,
    request: Request,
    session: DatabaseSession,
) -> PasswordResetRequestRead:
    token = request_password_reset(
        session, email=str(data.email), client_ip=_client_ip(request)
    )
    return PasswordResetRequestRead(
        message="If that active account exists, a password reset message has been generated.",
        reset_token=token if token and password_reset_token_exposed() else None,
    )


@public_router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def finish_password_reset(
    data: PasswordResetConfirmCreate, session: DatabaseSession
) -> None:
    try:
        confirm_password_reset(
            session,
            token=data.token,
            new_password=data.new_password,
            mfa_code=data.mfa_code,
            recovery_code=data.recovery_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@session_router.get("/me", response_model=UserRead)
def me(identity: HumanSession, session: DatabaseSession) -> UserRead:
    return _user_read(session, identity.user)


@session_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response, session: DatabaseSession, identity: HumanSession
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    _set_session_cookie(response, replacement.token)
    return _user_read(session, identity.user)


@session_router.get("/security", response_model=AccountSecurityRead)
def account_security(
    session: DatabaseSession, identity: HumanSession
) -> AccountSecurityRead:
    sessions = list(
        session.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == identity.user.id,
                AuthSession.revoked_at.is_(None),
            )
            .order_by(AuthSession.last_seen_at.desc())
        )
    )
    events = list(
        session.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.user_id == identity.user.id)
            .order_by(SecurityEvent.created_at.desc())
            .limit(50)
        )
    )
    permissions = effective_permissions(session, identity.user)
    privileged = identity.user.is_root or bool(
        permissions
        & {
            "access:manage",
            "api_credentials:manage",
            "changes:approve",
            "changes:execute",
        }
    )
    return AccountSecurityRead(
        mfa_enabled=identity.user.mfa_enabled,
        mfa_required=privileged and privileged_mfa_required(),
        sessions=[
            AuthSessionRead(
                id=item.id,
                current=item.id == identity.session.id,
                created_at=item.created_at,
                last_seen_at=item.last_seen_at,
                expires_at=item.expires_at,
                created_ip=item.created_ip,
                last_ip=item.last_ip,
                user_agent=item.user_agent,
                mfa_verified=item.mfa_verified_at is not None,
            )
            for item in sessions
        ],
        events=[SecurityEventRead.model_validate(item) for item in events],
    )


@session_router.post("/mfa/setup", response_model=MFASetupRead)
def setup_mfa(
    data: MFASetupCreate, session: DatabaseSession, identity: HumanSession
) -> MFASetupRead:
    try:
        secret, uri = begin_mfa_setup(
            session,
            user=identity.user,
            current_session=identity.session,
            current_password=data.current_password,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return MFASetupRead(secret=secret, provisioning_uri=uri)


@session_router.post("/mfa/confirm", response_model=MFAConfirmRead)
def confirm_mfa(
    data: MFAConfirmCreate, session: DatabaseSession, identity: HumanSession
) -> MFAConfirmRead:
    try:
        codes = confirm_mfa_setup(
            session,
            user=identity.user,
            current_session=identity.session,
            code=data.code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return MFAConfirmRead(recovery_codes=codes)


@session_router.delete("/mfa", response_model=UserRead)
def remove_mfa(
    data: MFADisableCreate,
    response: Response,
    session: DatabaseSession,
    identity: HumanSession,
) -> UserRead:
    try:
        replacement = disable_mfa(
            session,
            user=identity.user,
            current_session=identity.session,
            current_password=data.current_password,
            mfa_code=data.mfa_code,
            recovery_code=data.recovery_code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    _set_session_cookie(response, replacement.token)
    return _user_read(session, identity.user)


@session_router.post("/reauthenticate", response_model=UserRead)
def step_up(
    data: ReauthenticateCreate,
    response: Response,
    session: DatabaseSession,
    identity: HumanSession,
) -> UserRead:
    try:
        replacement = reauthenticate(
            session,
            user=identity.user,
            current_session=identity.session,
            password=data.password,
            mfa_code=data.mfa_code,
            recovery_code=data.recovery_code,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    _set_session_cookie(response, replacement.token)
    return _user_read(session, identity.user)


@session_router.post("/sessions/revoke-others", status_code=status.HTTP_204_NO_CONTENT)
def sign_out_other_devices(session: DatabaseSession, identity: HumanSession) -> None:
    _require_recent_reauthentication(identity)
    revoke_user_sessions(
        session,
        user=identity.user,
        current_session_id=identity.session.id,
        include_current=False,
    )


@session_router.post("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
def sign_out_all_devices(
    response: Response, session: DatabaseSession, identity: HumanSession
) -> None:
    _require_recent_reauthentication(identity)
    revoke_user_sessions(session, user=identity.user, include_current=True)
    _clear_session_cookie(response)


@session_router.post(
    "/security-events/{event_id}/acknowledge", response_model=SecurityEventRead
)
def acknowledge_event(
    event_id: int, session: DatabaseSession, identity: HumanSession
) -> SecurityEventRead:
    try:
        event = acknowledge_security_event(
            session, user=identity.user, event_id=event_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return SecurityEventRead.model_validate(event)


def _require_recent_reauthentication(identity: HumanSession) -> None:
    if not session_recently_reauthenticated(identity.session):
        raise AuthenticationError(
            "Re-enter your password before signing out other devices",
            code="reauthentication_required",
        )

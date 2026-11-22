"""Thin HTTP layer: validates input, delegates to application services."""
from fastapi import APIRouter, Depends, Request

from app.modules.identity.api.schemas import LoginRequest, TokenResponse, UserResponse
from app.modules.identity.application.contracts import CurrentUser
from app.modules.identity.application.dependencies import get_auth_service, get_current_user
from app.modules.identity.application.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=user.id, username=user.username, display_name=user.display_name,
        roles=list(user.roles), permissions=sorted(user.permissions),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    # The service applies back-off per (client address, username) after repeated failures.
    result = service.login(body.username, body.password, client=request.client.host if request.client else "unknown")
    return TokenResponse(
        access_token=result.access_token, token_type=result.token_type,
        expires_in=result.expires_in, user=_user_response(result.user),
    )


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.dependencies import get_user_repository
from app.config import Settings, get_settings
from app.db.user_repository import UserRepository
from app.security.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class SignupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    user = repository.get_by_email(request.email.lower())
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Incorrect email or password",
                    "details": {},
                }
            },
        )
    token = create_access_token(user["username"], settings)
    return LoginResponse(access_token=token, username=user["username"])


@router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def signup(
    request: SignupRequest,
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    if repository.get_by_username(request.username) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": {
                    "code": "USERNAME_TAKEN",
                    "message": "Username is already taken",
                    "details": {},
                }
            },
        )
    if repository.get_by_email(request.email) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "error": {
                    "code": "EMAIL_TAKEN",
                    "message": "Email is already registered",
                    "details": {},
                }
            },
        )
    repository.create_user(
        request.username,
        request.email.lower(),
        hash_password(request.password),
    )
    token = create_access_token(request.username, settings)
    return LoginResponse(access_token=token, username=request.username)


@router.get("/me")
def me(
    username: Annotated[str, Depends(get_current_user)],
) -> dict[str, str]:
    return {"username": username}

"""
Authentication router.
Part of Presentation layer - API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, get_user_repository, get_current_user, oauth2_scheme
from app.infrastructure.repositories.user_repository import UserRepository
from app.application.use_cases.auth_use_cases import (
    RegisterUserUseCase,
    LoginUserUseCase,
    RefreshTokenUseCase,
    LogoutUseCase,
    GetCurrentUserUseCase,
)
from app.presentation.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    RefreshRequest,
    RefreshResponse,
    LogoutRequest,
)
from app.infrastructure.services.jwt import extract_user_id_from_token
import base64
from typing import Optional

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Register a new user with email and password.

    - **email**: Valid email address
    - **password**: At least 8 characters
    - **full_name**: User's full name

    Returns user info, access token, and refresh token.
    """
    use_case = RegisterUserUseCase(user_repo, db)

    try:
        result = use_case.execute(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Login with email and password.

    - **email**: User's email address
    - **password**: User's password

    Returns user info, access token, and refresh token.
    """
    use_case = LoginUserUseCase(user_repo, db)

    try:
        result = use_case.execute(
            email=request.email,
            password=request.password,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/token", response_model=dict)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    OAuth2 compatible token endpoint.
    Used for Swagger UI authentication.

    - **username**: User's email address
    - **password**: User's password

    Returns access token for Bearer authentication.
    """
    use_case = LoginUserUseCase(user_repo)

    try:
        result = use_case.execute(
            email=form_data.username,  # OAuth2 uses 'username' field
            password=form_data.password,
        )
        return {
            "access_token": result["access_token"],
            "token_type": result["token_type"],
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user info.
    Requires valid JWT token in Authorization header.
    """
    return current_user


@router.post("/test-upload-simple")
async def test_upload_simple(file: UploadFile = File(...)):
    """Super simple test endpoint"""
    return {"status": "ok", "filename": file.filename}


@router.post("/upload-photo", response_model=UserResponse)
async def upload_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Upload profile photo for current user.

    - **file**: Image file (JPEG, PNG, GIF, WebP)

    Returns updated user info with photo_url as base64 data URL.
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: JPEG, PNG, GIF, WebP",
        )

    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}",
        )

    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 5MB",
        )

    # Convert to base64 data URL
    file_b64 = base64.b64encode(file_content).decode('utf-8')
    data_url = f"data:{file.content_type};base64,{file_b64}"

    # Get current user entity from database
    # current_user is a dict returned from GetCurrentUserUseCase
    user_id = current_user["id"]
    user = user_repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update user profile with photo URL
    user.update_profile(photo_url=data_url)

    # Save to database
    updated_user = user_repo.update(user)

    # Convert to response schema
    return UserResponse(
        id=str(updated_user.id),
        email=updated_user.email,
        full_name=updated_user.full_name,
        provider=updated_user.provider,
        is_active=updated_user.is_active,
        photo_url=updated_user.photo_url,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: RefreshRequest,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Refresh access token using a valid refresh token.

    - **refresh_token**: Valid refresh token from login/register

    Returns new access token and refresh token (token rotation).
    """
    use_case = RefreshTokenUseCase(user_repo, db)

    try:
        result = use_case.execute(refresh_token=request.refresh_token)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db),
):
    """
    Logout by revoking the refresh token.

    - **refresh_token**: Refresh token to revoke

    Returns 204 No Content on success.
    """
    use_case = LogoutUseCase(db)
    use_case.execute(refresh_token=request.refresh_token)
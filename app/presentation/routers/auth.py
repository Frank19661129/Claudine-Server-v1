"""
Authentication router.
Part of Presentation layer - API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.dependencies import get_db
from app.infrastructure.repositories.user_repository import UserRepository
from app.application.use_cases.auth_use_cases import (
    RegisterUserUseCase,
    LoginUserUseCase,
    GetCurrentUserUseCase,
)
from app.presentation.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
)
from app.infrastructure.services.jwt import extract_user_id_from_token

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth2 scheme for JWT token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Dependency to get user repository."""
    return UserRepository(db)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    """
    Dependency to get current authenticated user from JWT token.
    Raises HTTPException if token is invalid or user not found.
    """
    user_id = extract_user_id_from_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    use_case = GetCurrentUserUseCase(user_repo)
    user = use_case.execute(str(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Register a new user with email and password.

    - **email**: Valid email address
    - **password**: At least 8 characters
    - **full_name**: User's full name

    Returns user info and JWT access token.
    """
    use_case = RegisterUserUseCase(user_repo)

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
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Login with email and password.

    - **email**: User's email address
    - **password**: User's password

    Returns user info and JWT access token.
    """
    use_case = LoginUserUseCase(user_repo)

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

"""
Pydantic schemas for authentication endpoints.
Part of Presentation layer - request/response models.
"""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response schema for user data."""

    id: str
    email: str
    full_name: str
    provider: str
    is_active: bool
    photo_url: str | None = None


class AuthResponse(BaseModel):
    """Response schema for authentication (login/register)."""

    user: UserResponse
    access_token: str
    token_type: str = "bearer"

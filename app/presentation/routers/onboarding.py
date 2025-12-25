"""
Onboarding router.
Part of Presentation layer - API endpoints for user onboarding.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_db, get_user_repository, get_current_user
from app.infrastructure.repositories.user_repository import UserRepository
from app.application.use_cases.onboarding_use_cases import (
    StartEmailVerificationUseCase,
    VerifyEmailUseCase,
    SuggestInboxAddressUseCase,
    GenerateInboxAddressUseCase,
    SendInboxVerificationUseCase,
    VerifyInboxUseCase,
    StartPhoneVerificationUseCase,
    VerifyPhoneUseCase,
    CompleteOnboardingUseCase,
    GetOnboardingStatusUseCase,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# Request/Response schemas
class VerifyCodeRequest(BaseModel):
    code: str


class InboxPrefixRequest(BaseModel):
    prefix: Optional[str] = None


class PhoneRequest(BaseModel):
    phone_number: str


class VerifyInboxTokenRequest(BaseModel):
    token: str


class OnboardingStatusResponse(BaseModel):
    email: str
    email_verified: bool
    inbox_email: Optional[str]
    inbox_prefix: Optional[str]
    inbox_verified: bool
    phone_number: Optional[str]
    phone_verified: bool
    onboarding_completed: bool
    current_step: int


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: dict = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Get current onboarding status.

    Returns which step the user is on and what's completed.
    """
    use_case = GetOnboardingStatusUseCase(user_repo)
    try:
        result = use_case.execute(user_id=current_user["id"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/email/send-code")
async def send_email_verification_code(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Send email verification code.

    Step 1 of onboarding: verify the user's email address.
    """
    use_case = StartEmailVerificationUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/email/verify")
async def verify_email(
    request: VerifyCodeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Verify email with code.

    User enters the 6-digit code received via email.
    """
    use_case = VerifyEmailUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"], code=request.code)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/inbox/suggest")
async def suggest_inbox_address(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Suggest a unique PAI inbox address.

    Returns a guaranteed unique inbox address suggestion based on user's email.
    """
    use_case = SuggestInboxAddressUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/inbox/generate")
async def generate_inbox_address(
    request: InboxPrefixRequest = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Generate PAI inbox address.

    Step 2 of onboarding: create the user's personal PAI inbox.
    Validates uniqueness before saving.
    """
    use_case = GenerateInboxAddressUseCase(user_repo, db)
    try:
        prefix = request.prefix if request else None
        result = use_case.execute(user_id=current_user["id"], custom_prefix=prefix)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/inbox/send-verification")
async def send_inbox_verification(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Send inbox verification email.

    Step 3 of onboarding: sends email FROM user's PAI inbox TO their personal email
    with a verification link to confirm the inbox is working.
    """
    use_case = SendInboxVerificationUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/inbox/verify")
async def verify_inbox(
    request: VerifyInboxTokenRequest,
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Verify inbox with token from email link.

    This endpoint doesn't require authentication - the token in the email link
    is sufficient to identify and verify the user's inbox.
    """
    use_case = VerifyInboxUseCase(user_repo, db)
    try:
        result = use_case.execute(token=request.token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/phone/send-code")
async def send_phone_verification_code(
    request: PhoneRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Send phone verification code via SMS.

    Step 4 of onboarding: verify the user's phone number.
    """
    use_case = StartPhoneVerificationUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"], phone_number=request.phone_number)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/phone/verify")
async def verify_phone(
    request: VerifyCodeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Verify phone with code.

    User enters the 6-digit code received via SMS.
    """
    use_case = VerifyPhoneUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"], code=request.code)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/complete")
async def complete_onboarding(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """
    Complete the onboarding process.

    Marks the user as fully onboarded.
    """
    use_case = CompleteOnboardingUseCase(user_repo, db)
    try:
        result = use_case.execute(user_id=current_user["id"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

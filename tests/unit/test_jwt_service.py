"""
Unit tests for JWT service.
"""
import pytest
from uuid import uuid4, UUID
from app.infrastructure.services.jwt import (
    create_access_token,
    decode_access_token,
    extract_user_id_from_token,
)


def test_create_access_token():
    """Test JWT token creation."""
    user_id = uuid4()
    email = "test@example.com"
    provider = "local"

    token = create_access_token(user_id, email, provider)

    # Token should be a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token():
    """Test JWT token decoding."""
    user_id = uuid4()
    email = "test@example.com"
    provider = "local"

    token = create_access_token(user_id, email, provider)
    payload = decode_access_token(token)

    # Payload should contain expected fields
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["email"] == email
    assert payload["provider"] == provider
    assert "iat" in payload
    assert "exp" in payload


def test_decode_invalid_token():
    """Test decoding an invalid token."""
    invalid_token = "invalid.token.here"
    payload = decode_access_token(invalid_token)

    # Should return None for invalid token
    assert payload is None


def test_extract_user_id_from_token():
    """Test extracting user ID from token."""
    user_id = uuid4()
    email = "test@example.com"
    provider = "local"

    token = create_access_token(user_id, email, provider)
    extracted_id = extract_user_id_from_token(token)

    # Extracted ID should match original
    assert isinstance(extracted_id, UUID)
    assert extracted_id == user_id


def test_extract_user_id_from_invalid_token():
    """Test extracting user ID from invalid token."""
    invalid_token = "invalid.token.here"
    extracted_id = extract_user_id_from_token(invalid_token)

    # Should return None for invalid token
    assert extracted_id is None

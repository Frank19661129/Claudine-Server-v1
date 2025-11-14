"""
Unit tests for password service.
"""
import pytest
from app.infrastructure.services.password import hash_password, verify_password


def test_hash_password():
    """Test password hashing."""
    password = "my_secure_password_123"
    hashed = hash_password(password)

    # Hashed password should be different from plain text
    assert hashed != password

    # Hashed password should be a non-empty string
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_verify_password_correct():
    """Test password verification with correct password."""
    password = "my_secure_password_123"
    hashed = hash_password(password)

    # Correct password should verify successfully
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test password verification with incorrect password."""
    password = "my_secure_password_123"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    # Wrong password should not verify
    assert verify_password(wrong_password, hashed) is False


def test_hash_password_produces_different_hashes():
    """Test that same password produces different hashes (due to salt)."""
    password = "my_secure_password_123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Different hashes due to random salt
    assert hash1 != hash2

    # But both should verify the original password
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True

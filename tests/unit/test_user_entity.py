"""
Unit tests for User domain entity.
"""
import pytest
from app.domain.entities.user import User


def test_create_local_user():
    """Test creating a local user with password."""
    user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="local",
        hashed_password="hashed_password_123",
    )

    assert user.email == "test@example.com"
    assert user.full_name == "Test User"
    assert user.provider == "local"
    assert user.hashed_password == "hashed_password_123"
    assert user.is_active is True


def test_create_oauth_user():
    """Test creating an OAuth user without password."""
    user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="google",
    )

    assert user.email == "test@example.com"
    assert user.provider == "google"
    assert user.hashed_password is None
    assert user.is_active is True


def test_create_user_invalid_email():
    """Test that invalid email raises ValueError."""
    with pytest.raises(ValueError, match="Invalid email address"):
        User.create(
            email="invalid-email",
            full_name="Test User",
            provider="local",
            hashed_password="hashed",
        )


def test_create_user_invalid_provider():
    """Test that invalid provider raises ValueError."""
    with pytest.raises(ValueError, match="Invalid provider"):
        User.create(
            email="test@example.com",
            full_name="Test User",
            provider="invalid",
        )


def test_create_oauth_user_with_password():
    """Test that OAuth user with password raises ValueError."""
    with pytest.raises(ValueError, match="OAuth users cannot have passwords"):
        User.create(
            email="test@example.com",
            full_name="Test User",
            provider="google",
            hashed_password="should_not_have_this",
        )


def test_create_local_user_without_password():
    """Test that local user without password raises ValueError."""
    with pytest.raises(ValueError, match="Local users must have a password"):
        User.create(
            email="test@example.com",
            full_name="Test User",
            provider="local",
        )


def test_deactivate_user():
    """Test user deactivation."""
    user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="local",
        hashed_password="hashed",
    )

    assert user.is_active is True

    user.deactivate()

    assert user.is_active is False


def test_activate_user():
    """Test user activation."""
    user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="local",
        hashed_password="hashed",
    )

    user.deactivate()
    assert user.is_active is False

    user.activate()
    assert user.is_active is True


def test_update_profile():
    """Test profile update."""
    user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="local",
        hashed_password="hashed",
    )

    old_updated_at = user.updated_at

    user.update_profile(full_name="Updated Name")

    assert user.full_name == "Updated Name"
    assert user.updated_at > old_updated_at


def test_is_oauth_user():
    """Test OAuth user detection."""
    google_user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="google",
    )

    local_user = User.create(
        email="test2@example.com",
        full_name="Test User",
        provider="local",
        hashed_password="hashed",
    )

    assert google_user.is_oauth_user() is True
    assert local_user.is_oauth_user() is False


def test_is_local_user():
    """Test local user detection."""
    local_user = User.create(
        email="test@example.com",
        full_name="Test User",
        provider="local",
        hashed_password="hashed",
    )

    google_user = User.create(
        email="test2@example.com",
        full_name="Test User",
        provider="google",
    )

    assert local_user.is_local_user() is True
    assert google_user.is_local_user() is False

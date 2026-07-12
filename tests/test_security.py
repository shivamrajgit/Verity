import pytest

from src.utils.security import UnsafeTargetError, validate_target_url
from src.utils.url import is_same_domain


def test_private_targets_are_rejected_by_default() -> None:
    with pytest.raises(UnsafeTargetError, match="private or reserved"):
        validate_target_url("http://127.0.0.1:8000")


def test_private_targets_can_be_enabled_for_local_development() -> None:
    assert validate_target_url("http://127.0.0.1:8000", allow_private=True).startswith("http://")


def test_embedded_credentials_are_rejected() -> None:
    with pytest.raises(UnsafeTargetError, match="embedded credentials"):
        validate_target_url("https://user:password@example.com")


def test_allowed_domain_patterns_are_enforced() -> None:
    assert validate_target_url(
        "https://www.example.com",
        allowed_domains=["*.example.com"],
    )
    with pytest.raises(UnsafeTargetError, match="allowed domain"):
        validate_target_url("https://example.org", allowed_domains=["*.example.com"])


def test_ipv6_domain_comparison_does_not_collapse_all_addresses() -> None:
    assert not is_same_domain("http://[::2]/", "http://[::1]/")

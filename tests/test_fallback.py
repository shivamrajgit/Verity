from src.utils.fallback import generate_fallback_plan


def test_login_fallback_never_invents_credentials() -> None:
    plan = generate_fallback_plan("https://example.com/login", "test the login flow")
    steps = " ".join(plan.test_cases[0].steps).lower()

    assert "standard_user" not in steps
    assert "secret_sauce" not in steps
    assert "do not enter credentials" in steps

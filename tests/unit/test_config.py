from pathlib import Path

import pytest

from lipidence_modular.core.config import load_settings
from lipidence_modular.core.errors import ConfigurationError

BASE = {"LIPIDENCE_DATABASE_URL": "postgresql://u@h/db", "LIPIDENCE_STORAGE_DIR": "/tmp/x"}


def test_loads_required_values_and_defaults():
    settings = load_settings(BASE)
    assert settings.storage_dir == Path("/tmp/x")
    assert settings.environment == "development"
    assert settings.cookie_secure is False
    assert settings.session_ttl_minutes == 480


def test_production_sets_secure_cookie():
    assert load_settings({**BASE, "LIPIDENCE_ENV": "production"}).cookie_secure is True


@pytest.mark.parametrize("missing", sorted(BASE))
def test_inv07_missing_required_variable_is_explicit_error(missing):
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ConfigurationError, match=missing):
        load_settings(env)


@pytest.mark.parametrize(
    "extra",
    [
        {"LIPIDENCE_ENV": "staging"},
        {"LIPIDENCE_SESSION_TTL_MINUTES": "abc"},
        {"LIPIDENCE_SESSION_TTL_MINUTES": "0"},
    ],
)
def test_inv07_invalid_values_are_rejected(extra):
    with pytest.raises(ConfigurationError):
        load_settings({**BASE, **extra})

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Settings are lru_cached; clear between tests so env monkeypatches apply."""
    from llms_gen.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

from collections.abc import Iterator

import pytest

from vaipex_test_reliability.server import reference_application


@pytest.fixture(scope="session")
def base_url() -> Iterator[str]:
    with reference_application() as app_url:
        yield app_url

"""Tests standard tap features using the built-in SDK tests library."""

import pytest
from hotglue_singer_sdk.testing import get_standard_tap_tests

from tap_akeneo.tap import TapAkeneo

SAMPLE_CONFIG = {
    "base_url": "https://fixture.akeneo.example",
    "access_token": "fixture-token",
}

# _test_stream_connections makes live HTTP calls; excluded by default.
# Replace SAMPLE_CONFIG placeholders with real credentials and call it directly.
_STANDARD_TESTS = [
    t
    for t in get_standard_tap_tests(TapAkeneo, config=SAMPLE_CONFIG)
    if getattr(t, "__name__", "") != "_test_stream_connections"
]


@pytest.mark.parametrize("test_func", _STANDARD_TESTS)
def test_standard(test_func):
    """Run built-in SDK tap tests (CLI output and catalog discovery)."""
    test_func()

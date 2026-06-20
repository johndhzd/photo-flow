import pytest

from _helpers import build_root_config, touch


@pytest.fixture
def make_root_config():
    return build_root_config


@pytest.fixture
def touch_file():
    return touch

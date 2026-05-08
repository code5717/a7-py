import importlib

import pytest

from a7.backends import BACKENDS, get_backend, list_backends
from a7.backends.zig import ZigCodeGenerator


def test_only_zig_backend_is_registered():
    assert list(BACKENDS) == ["zig"]
    assert list_backends() == ["zig"]
    assert isinstance(get_backend("zig"), ZigCodeGenerator)


def test_removed_c_backend_is_not_importable():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("a7.backends.c")


def test_removed_generic_lowering_pass_is_not_importable():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("a7.passes.generic_lowering")


def test_get_backend_rejects_c_with_known_backends():
    with pytest.raises(ValueError, match="Available backends: zig"):
        get_backend("c")

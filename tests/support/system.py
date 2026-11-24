"""Marks for the tests that hold on Linux alone, each with its reason."""

import sys

import pytest

# The command warns when the keys file's mode lets other users read it. Windows keeps no modes of
# that kind, so every keys file there reads as open to others (backlog B-315).
needs_linux_file_modes = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows keeps no Linux file modes (backlog B-315)"
)

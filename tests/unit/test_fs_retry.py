"""Tests for Docker Desktop bind-mount FS retry helper."""

from __future__ import annotations

import pytest

from src.core.fs_retry import retry_os


def test_retry_os_succeeds_after_transient_deadlock() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError(35, "Resource deadlock avoided")
        return "ok"

    assert retry_os(flaky, retries=4, label="test") == "ok"
    assert calls["n"] == 3


def test_retry_os_raises_non_retryable() -> None:
    with pytest.raises(OSError) as excinfo:
        retry_os(lambda: (_ for _ in ()).throw(OSError(2, "No such file")), retries=3)
    assert excinfo.value.errno == 2

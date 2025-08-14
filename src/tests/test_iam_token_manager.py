import os
import pytest

from bookingassistant.iam import AsyncIamTokenManager


@pytest.mark.asyncio
async def test_env_token_skips_file(monkeypatch, tmp_path):
    monkeypatch.setenv("YANDEX_IAM_TOKEN", "token")
    missing = tmp_path / "missing.json"
    manager = AsyncIamTokenManager(sa_key_path=str(missing))
    assert await manager.get_token() == "token"


def test_missing_file_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("YANDEX_IAM_TOKEN", raising=False)
    missing = tmp_path / "missing.json"
    with pytest.raises(RuntimeError):
        AsyncIamTokenManager(sa_key_path=str(missing))

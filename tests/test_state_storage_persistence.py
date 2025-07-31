import importlib
import pytest

import state_storage


@pytest.mark.asyncio
async def test_state_persistence():
    uid = 123456
    await state_storage.clear_user_state(uid)
    await state_storage.set_user_state(uid, {"foo": "bar"})
    assert await state_storage.get_user_state(uid) == {"foo": "bar"}
    importlib.reload(state_storage)
    from state_storage import get_user_state, clear_user_state
    assert await get_user_state(uid) == {"foo": "bar"}
    await clear_user_state(uid)

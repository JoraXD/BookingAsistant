import json
import pytest
from aioresponses import aioresponses

import bookingassistant.parser as parser


def test_extract_json_multiple_objects():
    text = '{"foo": 1}\n{"bar": 2}'
    assert parser._extract_json(text) == '{"bar": 2}'


def test_extract_json_skips_empty_keys():
    text = '{"": 1}{"action": "show"}'
    assert parser._extract_json(text) == '{"action": "show"}'


@pytest.mark.asyncio
async def test_parse_history_request_handles_messy_answer():
    answer_text = '{"": 1}\n{"action": "show", "limit": "", "destination": ""}'
    payload = {
        "result": {"alternatives": [{"message": {"text": answer_text}}]}
    }
    with aioresponses() as m:
        m.post(parser.API_URL, payload=payload)
        data = await parser.parse_history_request("покажи поездки")
    assert data["action"] == "show"
    assert data["limit"] == 5

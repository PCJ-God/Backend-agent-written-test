"""OutputParser 单元测试。"""

import json

import pytest

from agent.output_parser import OutputParser
from agent.tool_registry import ToolRegistry


@pytest.fixture
def parser():
    return OutputParser()


def test_plain_text_reply(parser):
    p = parser.parse("今天天气不错")
    assert p.kind == "reply"
    assert p.answer == "今天天气不错"
    assert p.malformed is False


def test_valid_tool_call_json(parser):
    raw = json.dumps({
        "thinking": "算一下",
        "action": "tool_call",
        "tool_name": "calculator",
        "tool_args": {"expression": "1+2*3"},
    })
    p = parser.parse(raw, registry=ToolRegistry())
    assert p.kind == "tool_call"
    assert p.tool_name == "calculator"
    assert p.tool_args == {"expression": "1+2*3"}
    assert p.thinking == "算一下"


def test_noisy_json_with_markdown_fence(parser):
    raw = '好的。\n```json\n{"action":"tool_call","tool_name":"calculator","tool_args":{"expression":"2+2"}}\n```'
    p = parser.parse(raw, registry=ToolRegistry())
    assert p.kind == "tool_call"
    assert p.tool_name == "calculator"
    assert p.tool_args == {"expression": "2+2"}


def test_reply_with_final_answer(parser):
    raw = json.dumps({"thinking": "", "action": "reply", "final_answer": "你好"})
    p = parser.parse(raw)
    assert p.kind == "reply"
    assert p.answer == "你好"


def test_malformed_json_sets_flag(parser):
    p = parser.parse('{"action": "tool_call", "tool_name": }')
    assert p.malformed is True


def test_unregistered_tool_degrades_to_reply(parser):
    raw = json.dumps({"action": "tool_call", "tool_name": "nonexistent", "tool_args": {}})
    p = parser.parse(raw, registry=ToolRegistry())
    assert p.kind == "reply"


def test_tool_call_missing_name_is_malformed(parser):
    raw = json.dumps({"action": "tool_call", "tool_args": {}})
    p = parser.parse(raw, registry=ToolRegistry())
    assert p.kind == "reply"
    assert p.malformed is True


def test_empty_input_falls_back(parser):
    p = parser.parse("")
    assert p.kind == "reply"

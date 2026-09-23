import json

import pytest

from lazymind.chat.engine.tools.skill_listing import append_loaded_skill_invocations


SELECTED = {'skill_key': 'external/paper', 'revision_id': 'rev2', 'content': '# Paper\nFull instructions.'}


def history_for(payload, name='external/paper'):
    return [
        {'role': 'assistant', 'content': '', 'tool_calls': [{
            'id': 'previous-call', 'type': 'function',
            'function': {'name': 'get_skill', 'arguments': json.dumps({'name': name})},
        }]},
        {'role': 'tool', 'tool_call_id': 'previous-call', 'name': 'get_skill', 'content': json.dumps(payload)},
    ]


@pytest.mark.parametrize('payload', [
    {'status': 'failed', 'error': 'not found'},
    {'status': 'ok', 'content': ''},
    {'status': 'ok', 'content': 'truncated body', 'revision_id': 'rev2'},
    {'status': 'ok', 'content': SELECTED['content'], 'revision_id': 'rev1'},
    {'status': 'ok', 'content': ['not a document']},
    'malformed result',
])
def test_unsuccessful_or_stale_history_does_not_suppress_explicit_body(payload):
    history = history_for(payload)
    result = append_loaded_skill_invocations(history, [SELECTED])
    assert len(result) == 4
    assert len(history) == 2
    assert json.loads(result[-1]['content'])['content'] == SELECTED['content']
    assert result[-1]['tool_call_id'] != 'previous-call'


def test_tool_call_without_result_does_not_suppress_body():
    history = history_for({})[:1]
    assert len(append_loaded_skill_invocations(history, [SELECTED])) == 3


def test_same_basename_in_another_namespace_does_not_suppress_body():
    other = dict(SELECTED, skill_key='internal/paper')
    history = append_loaded_skill_invocations([], [other])
    assert len(append_loaded_skill_invocations(history, [SELECTED])) == 4


def test_two_explicit_namespaces_are_both_injected_in_one_turn():
    other = dict(SELECTED, skill_key='internal/paper')
    assert len(append_loaded_skill_invocations([], [other, SELECTED])) == 4


def test_successful_full_body_is_idempotent_and_respects_exclusion():
    history = append_loaded_skill_invocations([], [SELECTED, SELECTED])
    assert len(history) == 2
    assert append_loaded_skill_invocations(history, [SELECTED]) == history
    assert append_loaded_skill_invocations([], [SELECTED], excluded=['external/paper']) == []


def test_unpaired_tool_result_cannot_suppress_body():
    history = history_for({'status': 'ok', 'name': 'external/paper',
                           'revision_id': 'rev2', 'content': SELECTED['content']})[1:]
    assert len(append_loaded_skill_invocations(history, [SELECTED])) == 3

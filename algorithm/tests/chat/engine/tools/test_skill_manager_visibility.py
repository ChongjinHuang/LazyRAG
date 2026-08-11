from __future__ import annotations

import pytest

from lazyllm.tools.agent.skill_manager import SkillManager


class RecordingSandbox:
    def __init__(self):
        self.calls = []

    def execute_script(self, **kwargs):
        self.calls.append(kwargs)
        return {'status': 'ok', 'stdout': 'ok\n', 'stderr': '', 'exit_code': 0}


def _make_skill(base_dir, name: str) -> None:
    skill_dir = base_dir / name
    references_dir = skill_dir / 'references'
    scripts_dir = skill_dir / 'scripts'
    references_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    (skill_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {name}\n'
        f'description: {name} skill for visibility tests\n'
        '---\n'
        f'# {name}\n'
        'See references/guide.md and scripts/check.py.\n',
        encoding='utf-8',
    )
    (references_dir / 'guide.md').write_text(f'{name} guide\n', encoding='utf-8')
    (scripts_dir / 'check.py').write_text('print("ok")\n', encoding='utf-8')


def test_skill_list_filters_prompt_list_read_and_run(tmp_path):
    _make_skill(tmp_path, 'visible-skill')
    _make_skill(tmp_path, 'hidden-skill')
    sandbox = RecordingSandbox()

    manager = SkillManager(dir=str(tmp_path), skills=['visible-skill'], sandbox=sandbox)

    listing = manager.list_skill()
    assert 'visible-skill' in listing
    assert 'hidden-skill' not in listing

    prompt = manager.build_prompt()
    assert 'visible-skill' in prompt
    assert 'hidden-skill' not in prompt

    assert manager.get_skill('visible-skill')['status'] == 'ok'
    assert manager.get_skill('hidden-skill') == {'status': 'missing', 'name': 'hidden-skill'}

    visible_reference = manager.read_reference('visible-skill', 'references/guide.md')
    assert visible_reference['status'] == 'ok'
    assert visible_reference['content'] == 'visible-skill guide\n'
    assert manager.read_reference('hidden-skill', 'references/guide.md') == {
        'status': 'missing',
        'name': 'hidden-skill',
    }

    visible_result = manager.run_script('visible-skill', 'scripts/check.py')
    assert visible_result['status'] == 'ok'
    assert sandbox.calls
    assert sandbox.calls[0]['rel_path'] == 'scripts/check.py'

    hidden_result = manager.run_script('hidden-skill', 'scripts/check.py')
    assert hidden_result == {'status': 'missing', 'name': 'hidden-skill'}
    assert len(sandbox.calls) == 1


@pytest.mark.parametrize(
    'rel_path',
    ['../secret.md', '/tmp/secret.md', 'references/../SKILL.md', 'references//guide.md', r'references\guide.md'],
)
def test_read_reference_rejects_unsafe_rel_path(tmp_path, rel_path):
    _make_skill(tmp_path, 'visible-skill')
    manager = SkillManager(dir=str(tmp_path), skills=['visible-skill'])

    result = manager.read_reference('visible-skill', rel_path)

    assert result['status'] == 'error'
    assert result['name'] == 'visible-skill'
    assert 'rel_path' in result['error']


def test_read_reference_uses_normalized_safe_rel_path(tmp_path):
    _make_skill(tmp_path, 'visible-skill')
    manager = SkillManager(dir=str(tmp_path), skills=['visible-skill'])

    result = manager.read_reference('visible-skill', 'references/guide.md')

    assert result['status'] == 'ok'
    assert result['content'] == 'visible-skill guide\n'

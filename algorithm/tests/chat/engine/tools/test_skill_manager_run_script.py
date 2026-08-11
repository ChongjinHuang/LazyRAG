from __future__ import annotations

import os

from lazyllm.tools.agent.skill_manager import SkillManager


class MaterializingFS:
    def __init__(self):
        self.materialized = []

    def materialize_dir(self, path: str, local_dir: str):
        self.materialized.append((path, local_dir))
        script_dir = os.path.join(local_dir, 'core')
        os.makedirs(script_dir, exist_ok=True)
        with open(os.path.join(script_dir, 'check.py'), 'w', encoding='utf-8') as fh:
            fh.write('print("ok")\n')
        return {
            'source_path': path,
            'local_dir': local_dir,
            'materialized': True,
            'files': ['core/check.py'],
        }


class RecordingSandbox:
    def __init__(self):
        self.calls = []

    def execute_script(self, **kwargs):
        self.calls.append(kwargs)
        return {'status': 'ok', 'stdout': 'ok\n', 'stderr': '', 'exit_code': 0}


def test_run_script_uses_fs_materialize_dir_without_source_specific_branch():
    fs = MaterializingFS()
    sandbox = RecordingSandbox()

    manager = SkillManager(dir='', fs=fs, sandbox=sandbox)
    manager._skills_index = {
        'pkg': {
            'name': 'pkg',
            'path': 'remote://skills/coding/pkg',
            'skill_md': 'remote://skills/coding/pkg/SKILL.md',
        }
    }

    result = manager.run_script('pkg', 'core/check.py', args=['--fast'])

    assert result['status'] == 'ok'
    assert fs.materialized[0][0] == 'remote://skills/coding/pkg'
    assert sandbox.calls[0]['rel_path'] == 'core/check.py'
    assert sandbox.calls[0]['args'] == ['--fast']
    assert sandbox.calls[0]['cwd'] == '.'


def test_run_script_reports_missing_materialized_script():
    fs = MaterializingFS()
    manager = SkillManager(dir='', fs=fs, sandbox=RecordingSandbox())
    manager._skills_index = {
        'pkg': {
            'name': 'pkg',
            'path': 'remote://skills/coding/pkg',
            'skill_md': 'remote://skills/coding/pkg/SKILL.md',
        }
    }

    result = manager.run_script('pkg', 'core/missing.py')

    assert result['status'] == 'missing'
    assert result['path'].endswith('/core/missing.py')
    assert fs.materialized[0][0] == 'remote://skills/coding/pkg'

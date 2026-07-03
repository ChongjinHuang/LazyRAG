import importlib.util
import sys
import types
from pathlib import Path


def _load_online_search_module():
    fake_lazyllm = types.ModuleType('lazyllm')
    fake_lazyllm.LOG = types.SimpleNamespace(
        warning=lambda *_args, **_kwargs: None,
        exception=lambda *_args, **_kwargs: None,
    )

    fake_feishu = types.ModuleType('lazyllm.tools.fs.supplier.feishu')
    class FakeFeishuWikiFS:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_feishu.FeishuWikiFS = FakeFeishuWikiFS

    fake_notion = types.ModuleType('lazyllm.tools.fs.supplier.notion')
    fake_notion.NotionFS = object

    fake_infra = types.ModuleType('lazymind.chat.engine.tools.infra')
    fake_infra.handle_tool_errors = lambda func: func
    fake_infra.tool_success = lambda tool, result: {
        'success': True,
        'tool': tool,
        'result': result,
    }

    modules = {
        'lazyllm': fake_lazyllm,
        'lazyllm.tools.fs.supplier.feishu': fake_feishu,
        'lazyllm.tools.fs.supplier.notion': fake_notion,
        'lazymind.chat.engine.tools.infra': fake_infra,
    }
    old_modules = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        path = Path('algorithm/lazymind/chat/engine/tools/online_search.py')
        spec = importlib.util.spec_from_file_location('_online_search_under_test', path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in old_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


class _FakeFeishuFS:
    def __init__(self):
        self.search_calls = []
        self.find_calls = []

    def search(self, query, space_id='', page_size=20):
        self.search_calls.append((query, space_id, page_size))
        return [
            {'title': 'Project Plan', 'node_token': 'node1'},
            {'title': 'Meeting Notes', 'node_token': 'node2'},
        ]

    def find(self, pattern, space_id='', max_results=50):
        self.find_calls.append((pattern, space_id, max_results))
        return [{'title': 'Project Plan', 'node_token': 'node1'}]


class _FakeNotionFS:
    def __init__(self):
        self.search_calls = []
        self.find_calls = []

    def search(self, query, limit=20, scope='', title_pattern=''):
        self.search_calls.append((query, limit, scope, title_pattern))
        return [{'title': 'Project Plan', 'notion_path': 'notion:/~page/page1'}]

    def find(self, pattern, limit=50, scope=''):
        self.find_calls.append((pattern, limit, scope))
        return [{'title': 'Project Plan', 'notion_path': 'notion:/~page/page1'}]


def test_get_feishu_fs_returns_wiki_filesystem():
    online_search = _load_online_search_module()

    fs = online_search._get_feishu_fs()

    assert isinstance(fs, online_search.FeishuWikiFS)
    assert fs.kwargs == {'dynamic_auth': True}


def test_search_online_passes_source_specific_scopes(monkeypatch):
    online_search = _load_online_search_module()
    feishu = _FakeFeishuFS()
    notion = _FakeNotionFS()
    monkeypatch.setattr(online_search, '_get_feishu_fs', lambda: feishu)
    monkeypatch.setattr(online_search, '_get_notion_fs', lambda: notion)

    payload = online_search.OnlineSearchToolGroup().search_online(
        'Project',
        sources=['feishu', 'notion'],
        filename_scope='Plan$',
        feishu_space_id='wikcnScope',
        notion_scope='notion:/~data_source/11111111222233334444555555555555',
        max_results=8,
    )

    assert payload['success'] is True
    assert feishu.search_calls == [('Project', 'wikcnScope', 8)]
    assert notion.search_calls == [
        ('Project', 8, 'notion:/~data_source/11111111222233334444555555555555', 'Plan$')
    ]
    assert payload['result']['feishu']['items'] == [{'title': 'Project Plan', 'node_token': 'node1'}]


def test_find_online_passes_source_specific_scopes(monkeypatch):
    online_search = _load_online_search_module()
    feishu = _FakeFeishuFS()
    notion = _FakeNotionFS()
    monkeypatch.setattr(online_search, '_get_feishu_fs', lambda: feishu)
    monkeypatch.setattr(online_search, '_get_notion_fs', lambda: notion)

    payload = online_search.OnlineSearchToolGroup().find_online(
        '^Project',
        sources=['feishu', 'notion'],
        feishu_space_id='wikcnScope',
        notion_scope='notion:/~database/11111111222233334444555555555555',
        max_results=10,
    )

    assert payload['success'] is True
    assert feishu.find_calls == [('^Project', 'wikcnScope', 10)]
    assert notion.find_calls == [
        ('^Project', 10, 'notion:/~database/11111111222233334444555555555555')
    ]


def test_sources_are_deduplicated_and_total_results_are_capped(monkeypatch):
    online_search = _load_online_search_module()
    feishu = _FakeFeishuFS()
    notion = _FakeNotionFS()
    monkeypatch.setattr(online_search, '_get_feishu_fs', lambda: feishu)
    monkeypatch.setattr(online_search, '_get_notion_fs', lambda: notion)

    payload = online_search.OnlineSearchToolGroup().search_online(
        'Project', sources=['feishu', 'feishu', 'notion'], max_results=2,
    )

    assert feishu.search_calls == [('Project', '', 2)]
    assert notion.search_calls == [('Project', 2, '', '')]
    assert sum(group['total'] for group in payload['result'].values()) == 2
    assert payload['result']['feishu']['total'] == 1
    assert payload['result']['notion']['total'] == 1

# Copyright (c) 2026 LazyAGI. All rights reserved.
"""Online search tools for Feishu wiki and Notion knowledge bases.

These tools search the LIVE online sources (not the locally indexed
knowledge base) using the official Feishu and Notion APIs.  The agent
can call them when the user asks to find something in their Feishu
wiki or Notion workspace.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import lazyllm
from lazyllm.tools.fs.supplier.feishu import FeishuFS, FeishuWikiFS
from lazyllm.tools.fs.supplier.notion import NotionFS

from lazymind.chat.engine.tools.infra import handle_tool_errors, tool_success


_DEFAULT_MAX_RESULTS = 10
_DEFAULT_FIND_MAX_RESULTS = 20


def _get_feishu_fs() -> FeishuWikiFS:
    """Return a FeishuWikiFS instance with per-request dynamic auth."""
    return FeishuFS(space_id='dynamic', dynamic_auth=True)


def _get_notion_fs() -> NotionFS:
    """Return a NotionFS instance with per-request dynamic auth."""
    return NotionFS(dynamic_auth=True)


def _normalize_sources(sources: Optional[List[str]]) -> List[str]:
    """Normalize and validate the sources list."""
    valid = {'feishu', 'notion'}
    if not sources:
        return ['feishu', 'notion']
    normalized = []
    for s in sources:
        s = (s or '').strip().lower()
        if s in valid:
            normalized.append(s)
    return normalized if normalized else ['feishu', 'notion']


def _filter_by_title_pattern(items: List[Dict[str, Any]], pattern: str) -> List[Dict[str, Any]]:
    pattern = (pattern or '').strip()
    if not pattern:
        return items
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f'Invalid filename_scope regex pattern: {exc}') from exc
    return [
        item for item in items
        if regex.search(item.get('title') or item.get('name') or '')
    ]


class OnlineSearchToolGroup:
    """Search online Feishu wiki and Notion knowledge bases.

    These tools call the official Feishu / Notion APIs directly to
    search the LIVE online sources — NOT the locally indexed knowledge
    base.  Use them when the user asks to search their Feishu wiki or
    Notion workspace for documents.
    """

    __public_apis__ = ['search_online', 'find_online']

    @handle_tool_errors
    def search_online(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        scope: str = '',
        filename_scope: str = '',
        feishu_space_id: str = '',
        notion_scope: str = '',
        max_results: int = _DEFAULT_MAX_RESULTS,
    ) -> Dict[str, Any]:
        """Search online Feishu wiki and/or Notion for content matching keywords.

        Uses the official Feishu wiki search API and Notion search API to
        find documents in the LIVE online sources. This is different from
        kb_search which searches the locally indexed knowledge base.

        IMPORTANT: Each call handles exactly ONE search intent. If the user
        asks about multiple unrelated topics, call this tool separately for
        each topic.

        Args:
            query: One or more keywords to search for. Use spaces to separate
                multiple keywords.
            sources: Which sources to search. Options: ['feishu', 'notion'].
                Defaults to both.  Pass ['feishu'] for Feishu wiki only, or
                ['notion'] for Notion only.
            scope: Backward-compatible Feishu wiki space_id. Prefer
                feishu_space_id for new calls.
            filename_scope: Optional filename/title regex. The search still
                uses the official online APIs, then filters returned document
                titles by this regex.
            feishu_space_id: Optional Feishu wiki space_id. Feishu search uses
                the official wiki/v2/spaces/{space_id}/search API.
            notion_scope: Optional Notion database or data_source id/path
                (for example notion:/~data_source/<id>) to restrict search to
                one Notion knowledge base.
            max_results: Maximum total results (default 10, max 50).

        Returns:
            Search results grouped by source, each with title, url, snippet,
            and source metadata.
        """
        query = (query or '').strip()
        if not query:
            raise ValueError('query is required and must be a non-empty string')
        max_results = max(1, min(int(max_results), 50))
        sources = _normalize_sources(sources)

        result: Dict[str, Any] = {}
        per_source = max(1, max_results // len(sources))
        feishu_scope = feishu_space_id or scope

        if 'feishu' in sources:
            try:
                fs = _get_feishu_fs()
                feishu_results = fs.search(
                    query, space_id=feishu_scope, page_size=per_source,
                )
                feishu_results = _filter_by_title_pattern(feishu_results, filename_scope)
                result['feishu'] = {
                    'total': len(feishu_results),
                    'items': feishu_results,
                }
            except Exception as exc:
                lazyllm.LOG.warning(f'Feishu search_online failed: {exc}')
                result['feishu'] = {
                    'total': 0,
                    'items': [],
                    'error': str(exc),
                }

        if 'notion' in sources:
            try:
                fs = _get_notion_fs()
                notion_results = fs.search(
                    query, limit=per_source, scope=notion_scope,
                    title_pattern=filename_scope,
                )
                result['notion'] = {
                    'total': len(notion_results),
                    'items': notion_results,
                }
            except Exception as exc:
                lazyllm.LOG.warning(f'Notion search_online failed: {exc}')
                result['notion'] = {
                    'total': 0,
                    'items': [],
                    'error': str(exc),
                }

        return tool_success('search_online', result)

    @handle_tool_errors
    def find_online(
        self,
        pattern: str,
        sources: Optional[List[str]] = None,
        scope: str = '',
        feishu_space_id: str = '',
        notion_scope: str = '',
        max_results: int = _DEFAULT_FIND_MAX_RESULTS,
    ) -> Dict[str, Any]:
        """Find files/documents by name pattern (regex) in Feishu wiki and/or Notion.

        Searches ONLY filenames/titles — not document content — using a
        regular expression. This is useful when you know part of a document
        name but not its exact location.

        Uses case-insensitive matching. Common regex examples:
        - "report" matches any title containing "report"
        - "^2024" matches titles starting with "2024"
        - "(设计|方案)" matches titles containing either Chinese term

        Args:
            pattern: Regular expression pattern to match against document
                titles. Case-insensitive.
            sources: Which sources to search. Options: ['feishu', 'notion'].
                Defaults to both.
            scope: Backward-compatible Feishu wiki space_id. Prefer
                feishu_space_id for new calls.
            feishu_space_id: Optional Feishu wiki space_id.
            notion_scope: Optional Notion database or data_source id/path.
            max_results: Maximum total results (default 20, max 100).

        Returns:
            Matching documents grouped by source, each with title, url/path,
            and source metadata.
        """
        pattern = (pattern or '').strip()
        if not pattern:
            raise ValueError('pattern is required and must be a non-empty string')
        max_results = max(1, min(int(max_results), 100))
        sources = _normalize_sources(sources)

        result: Dict[str, Any] = {}
        per_source = max(1, max_results // len(sources))
        feishu_scope = feishu_space_id or scope

        if 'feishu' in sources:
            try:
                fs = _get_feishu_fs()
                feishu_results = fs.find(
                    pattern, space_id=feishu_scope, max_results=per_source,
                )
                result['feishu'] = {
                    'total': len(feishu_results),
                    'items': feishu_results,
                }
            except Exception as exc:
                lazyllm.LOG.warning(f'Feishu find_online failed: {exc}')
                result['feishu'] = {
                    'total': 0,
                    'items': [],
                    'error': str(exc),
                }

        if 'notion' in sources:
            try:
                fs = _get_notion_fs()
                notion_results = fs.find(pattern, limit=per_source, scope=notion_scope)
                result['notion'] = {
                    'total': len(notion_results),
                    'items': notion_results,
                }
            except Exception as exc:
                lazyllm.LOG.warning(f'Notion find_online failed: {exc}')
                result['notion'] = {
                    'total': 0,
                    'items': [],
                    'error': str(exc),
                }

        return tool_success('find_online', result)

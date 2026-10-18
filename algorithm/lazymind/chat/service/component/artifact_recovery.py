"""Recover complete inline deliverables when an Agent omits the publish tool."""

from __future__ import annotations

import re
from html import unescape
from typing import Any


_HTML_DOCUMENT = re.compile(r'<!doctype\s+html\b[\s\S]*?</html\s*>', re.IGNORECASE)
_HTML_ROOT = re.compile(r'<html\b[\s\S]*?</html\s*>', re.IGNORECASE)
_EDITABLE_OPEN = re.compile(r'^```editable\s*$', re.IGNORECASE)
_TITLE = re.compile(r'<title\b[^>]*>(.*?)</title\s*>', re.IGNORECASE | re.DOTALL)
_HEADING = re.compile(r'^#\s+(.+)$', re.MULTILINE)


def _filename(title: str, suffix: str) -> str:
    cleaned = re.sub(r'[\\/\x00-\x1f\x7f:*?"<>|]+', ' ', unescape(title))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .')[:180]
    return f'{cleaned or "生成产物"}.{suffix}'


def complete_inline_artifact(final_result: Any) -> tuple[str, str] | None:
    """Return a complete HTML or editable document, never partial prose."""
    raw = final_result.get('text') or final_result.get('message') if isinstance(final_result, dict) else final_result
    text = str(raw or '')
    html = _HTML_DOCUMENT.search(text) or _HTML_ROOT.search(text)
    if html:
        content = html.group(0)
        title = _TITLE.search(content)
        return _filename(title.group(1) if title else '图示', 'html'), content
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not _EDITABLE_OPEN.match(line.strip()):
            continue
        depth = 1
        content_lines = []
        for body_line in lines[index + 1:]:
            marker = body_line.strip()
            if marker.startswith('```'):
                if marker == '```':
                    depth -= 1
                    if depth == 0:
                        break
                else:
                    depth += 1
            content_lines.append(body_line)
        if depth != 0:
            return None
        content = '\n'.join(content_lines).strip()
        if not content:
            return None
        heading = _HEADING.search(content)
        return _filename(heading.group(1) if heading else '文档', 'md'), content
    return None

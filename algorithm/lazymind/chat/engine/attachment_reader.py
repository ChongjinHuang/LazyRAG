from __future__ import annotations

import math
import re
import time
import zipfile
from decimal import Decimal
from functools import lru_cache
from numbers import Integral, Real
from pathlib import Path
from typing import List, Optional

import lazyllm
from lazyllm import AutoModel, LOG
from lazyllm.components.formatter import encode_query_with_filepaths

from lazymind.chat.config import (
    CHAT_DOCUMENT_EXTENSIONS,
    CHAT_SPREADSHEET_EXTENSIONS,
    CHAT_TEXT_EXTENSIONS,
    IMAGE_EXTENSIONS,
)
from lazymind.chat.engine.prompts import VISION_EXTRACT_DEFAULT_INSTRUCTION
from lazymind.config import config as _cfg
from lazymind.model_config import is_model_role_available

_SUPPORTED_ATTACHMENT_LABEL = (
    'images, Office/PDF documents, Excel spreadsheets, and common plain-text files'
)
_PROMPT_TEMPLATE_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')
_MAX_TEXT_ATTACHMENT_CHARS = 200_000
_MAX_DOCUMENT_ATTACHMENT_CHARS = 200_000
_MAX_SPREADSHEET_ATTACHMENT_CHARS = 200_000
_MAX_SPREADSHEET_ROWS_PER_SHEET = 5_000
_MAX_SPREADSHEET_SHEETS = 20
_MAX_TABULAR_FILE_BYTES = 100 * 1024 * 1024
_MAX_XLSX_ARCHIVE_ENTRIES = 10_000
_MAX_XLSX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_MAX_XLSX_COMPRESSION_RATIO = 200
_DELIMITED_TEXT_EXTENSIONS = ('.csv', '.tsv')


def _sanitize_for_prompt_template(text: str) -> str:
    # ChatPrompter scans instruction for `{word}` placeholders. Escape attachment
    # bodies only at prompt-build time so OCR/PDF caches stay canonical.
    if not text:
        return text
    return _PROMPT_TEMPLATE_PLACEHOLDER_RE.sub(r'{ \1 }', text)


@lru_cache(maxsize=1)
def _get_document_reader():
    from lazymind.chat.runtime_loader import ensure_rag_runtime
    ensure_rag_runtime()
    from lazyllm.tools.rag.readers.ocrReader import DynamicPDFReader

    return DynamicPDFReader(
        image_cache_dir=_cfg['ocr_cache_dir'],
        timeout=3600,
    )


def _suffix(path: str) -> str:
    return Path(path).suffix.lower()


def is_chat_image_file(path: str) -> bool:
    return _suffix(path) in IMAGE_EXTENSIONS


def is_chat_document_file(path: str) -> bool:
    return _suffix(path) in CHAT_DOCUMENT_EXTENSIONS


def is_chat_spreadsheet_file(path: str) -> bool:
    return _suffix(path) in CHAT_SPREADSHEET_EXTENSIONS


def is_chat_text_file(path: str) -> bool:
    return _suffix(path) in CHAT_TEXT_EXTENSIONS


def is_chat_attachment_file(path: str) -> bool:
    return (
        is_chat_image_file(path)
        or is_chat_document_file(path)
        or is_chat_spreadsheet_file(path)
        or is_chat_text_file(path)
    )


def filter_chat_image_files(files: List[str]) -> List[str]:
    return [path for path in files if is_chat_image_file(path)]


def filter_chat_document_files(files: List[str]) -> List[str]:
    return [path for path in files if is_chat_document_file(path)]


def _file_digest(path: str) -> str:
    try:
        stat = Path(path).stat()
        return f'mtime={stat.st_mtime:.0f},size={stat.st_size}'
    except OSError:
        return 'stat_unavailable'


def _log_parse_start(path: str, *, kind: str) -> float:
    reader_use_cache = bool(lazyllm.config['reader_use_cache'])
    name = Path(path).name
    LOG.info(
        f'[AttachmentReader] parse start file={name} kind={kind} '
        f'digest={_file_digest(path)} reader_use_cache={reader_use_cache} path={path}'
    )
    return time.perf_counter()


def _log_parse_done(
    path: str,
    *,
    kind: str,
    started_at: float,
    body: str,
) -> None:
    reader_use_cache = bool(lazyllm.config['reader_use_cache'])
    elapsed = time.perf_counter() - started_at
    name = Path(path).name
    LOG.info(
        f'[AttachmentReader] parse done file={name} kind={kind} '
        f'elapsed={elapsed:.3f}s chars={len(body)} reader_use_cache={reader_use_cache} '
        f'digest={_file_digest(path)} path={path}'
    )


def read_chat_document_text(file_path: str) -> str:
    started_at = _log_parse_start(file_path, kind='document')
    if _suffix(file_path) == '.docx':
        try:
            body = _read_docx_text(file_path)
            if not body.strip():
                raise ValueError('DOCX contains no locally extractable text')
            _log_parse_done(file_path, kind='document-local-docx', started_at=started_at, body=body)
            return body
        except Exception as exc:
            LOG.warning(
                f'[AttachmentReader] local DOCX parse failed; falling back to OCR: '
                f'file={Path(file_path).name} error={exc}'
            )
    reader = _get_document_reader()
    nodes = reader(file_path)
    parts: List[str] = []
    for node in nodes or []:
        text = str(getattr(node, 'text', '') or '').strip()
        if text:
            parts.append(text)
    body = '\n\n'.join(parts)
    _log_parse_done(file_path, kind='document', started_at=started_at, body=body)
    return body


def _read_docx_text(file_path: str, max_chars: int = _MAX_DOCUMENT_ATTACHMENT_CHARS) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(file_path)
    parts: List[str] = []
    current_chars = 0

    def append(value: str) -> bool:
        nonlocal current_chars
        text = str(value or '').strip()
        if not text:
            return False
        remaining = max_chars - current_chars
        if remaining <= 0:
            return True
        parts.append(text[:remaining])
        current_chars += min(len(text), remaining)
        return len(text) > remaining or current_chars >= max_chars

    for child in document.element.body.iterchildren():
        if child.tag.endswith('}p'):
            if append(Paragraph(child, document).text):
                break
        elif child.tag.endswith('}tbl'):
            table = Table(child, document)
            for row in table.rows:
                if append('\t'.join(cell.text.strip() for cell in row.cells)):
                    break
            if current_chars >= max_chars:
                break
    body = '\n'.join(parts)
    if current_chars >= max_chars:
        body += f'\n\n[Attachment truncated after {max_chars} characters.]'
    return body


def read_chat_text_file(file_path: str, max_chars: int = _MAX_TEXT_ATTACHMENT_CHARS) -> str:
    started_at = _log_parse_start(file_path, kind='text')
    with open(file_path, 'r', encoding='utf-8', errors='strict') as file:
        body = file.read(max_chars + 1)
    if '\x00' in body:
        raise ValueError('Attachment contains NUL bytes and is not a plain-text file')
    if len(body) > max_chars:
        body = (
            body[:max_chars]
            + f'\n\n[Attachment truncated after {max_chars} characters.]'
        )
    _log_parse_done(file_path, kind='text', started_at=started_at, body=body)
    return body


def _format_numeric_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            return ''
        if value == value.to_integral_value():
            return str(value.to_integral_value())
        return format(value, '.12g')
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            return ''
        if number.is_integer():
            return str(int(number))
        return format(number, '.12g')
    return str(value)


def _build_numeric_summary(frame, *, scope: str) -> str:
    import pandas as pd

    rows = []
    for column in frame.columns:
        values = pd.to_numeric(frame[column], errors='coerce').dropna()
        if values.empty:
            continue
        if pd.api.types.is_integer_dtype(values.dtype):
            exact_values = [int(value) for value in values]
            total = sum(exact_values)
            mean = Decimal(total) / len(exact_values)
            minimum = min(exact_values)
            maximum = max(exact_values)
        else:
            total = values.sum()
            mean = values.mean()
            minimum = values.min()
            maximum = values.max()
        rows.append({
            'column': str(column),
            'count': len(values.index),
            'sum': _format_numeric_value(total),
            'mean': _format_numeric_value(mean),
            'min': _format_numeric_value(minimum),
            'max': _format_numeric_value(maximum),
        })
    if not rows:
        return ''
    summary = pd.DataFrame(rows).to_csv(index=False, lineterminator='\n').rstrip()
    return (
        f'## Deterministic Numeric Summary: {scope}\n'
        'Computed from the included rows. Use these values to verify aggregate KPIs.\n'
        f'{summary}'
    )


def _validate_tabular_file(file_path: str) -> None:
    path = Path(file_path)
    size = path.stat().st_size
    if size > _MAX_TABULAR_FILE_BYTES:
        raise ValueError(
            f'Tabular attachment exceeds the {_MAX_TABULAR_FILE_BYTES // (1024 * 1024)} MiB limit'
        )
    if path.suffix.lower() != '.xlsx':
        return
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > _MAX_XLSX_ARCHIVE_ENTRIES:
                raise ValueError('XLSX archive contains too many entries')
            total_uncompressed = 0
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise ValueError('Encrypted XLSX archives are not supported')
                total_uncompressed += entry.file_size
                if total_uncompressed > _MAX_XLSX_UNCOMPRESSED_BYTES:
                    raise ValueError('XLSX archive expands beyond the safe size limit')
                if entry.file_size > 0:
                    if entry.compress_size == 0:
                        raise ValueError('XLSX archive contains an invalid compressed entry')
                    if entry.file_size / entry.compress_size > _MAX_XLSX_COMPRESSION_RATIO:
                        raise ValueError('XLSX archive contains a suspicious compression ratio')
    except zipfile.BadZipFile as exc:
        raise ValueError('XLSX attachment is not a valid ZIP workbook') from exc


def _truncate_attachment(body: str, max_chars: int) -> str:
    if len(body) <= max_chars:
        return body
    return body[:max_chars] + f'\n\n[Attachment truncated after {max_chars} characters.]'


def read_chat_delimited_file(
    file_path: str,
    *,
    max_chars: int = _MAX_TEXT_ATTACHMENT_CHARS,
    max_rows: int = _MAX_SPREADSHEET_ROWS_PER_SHEET,
) -> str:
    import pandas as pd

    started_at = _log_parse_start(file_path, kind='delimited')
    _validate_tabular_file(file_path)
    separator = '\t' if _suffix(file_path) == '.tsv' else ','
    frame = pd.read_csv(file_path, sep=separator, nrows=max_rows + 1)
    rows_truncated = len(frame.index) > max_rows
    if rows_truncated:
        frame = frame.iloc[:max_rows]
    summary = _build_numeric_summary(frame, scope=Path(file_path).name)
    table = frame.to_csv(index=False, sep=separator, na_rep='', lineterminator='\n').rstrip()
    body = '\n\n'.join(part for part in (summary, '## Data\n' + table) if part)
    if rows_truncated:
        body += f'\n[File truncated after {max_rows} data rows.]'
    body = _truncate_attachment(body, max_chars)
    _log_parse_done(file_path, kind='delimited', started_at=started_at, body=body)
    return body


def read_chat_spreadsheet_file(
    file_path: str,
    *,
    max_chars: int = _MAX_SPREADSHEET_ATTACHMENT_CHARS,
    max_rows_per_sheet: int = _MAX_SPREADSHEET_ROWS_PER_SHEET,
    max_sheets: int = _MAX_SPREADSHEET_SHEETS,
) -> str:
    import pandas as pd

    started_at = _log_parse_start(file_path, kind='spreadsheet')
    _validate_tabular_file(file_path)
    sections: List[str] = []
    used_chars = 0
    content_truncated = False
    with pd.ExcelFile(file_path) as workbook:
        sheet_names = workbook.sheet_names
        for sheet_name in sheet_names[:max_sheets]:
            if used_chars >= max_chars:
                content_truncated = True
                break
            frame = pd.read_excel(
                workbook,
                sheet_name=sheet_name,
                dtype=object,
                nrows=max_rows_per_sheet + 1,
            )
            rows_truncated = len(frame.index) > max_rows_per_sheet
            if rows_truncated:
                frame = frame.iloc[:max_rows_per_sheet]
            csv_content = frame.to_csv(index=False, na_rep='', lineterminator='\n')
            summary = _build_numeric_summary(frame, scope=sheet_name)
            section = f'## Sheet: {sheet_name}\n{csv_content}'.rstrip()
            if summary:
                section = f'{summary}\n\n{section}'
            if rows_truncated:
                section += f'\n[Sheet truncated after {max_rows_per_sheet} data rows.]'
            separator_chars = 2 if sections else 0
            remaining = max_chars - used_chars - separator_chars
            if remaining <= 0:
                content_truncated = True
                break
            if len(section) > remaining:
                sections.append(section[:remaining])
                used_chars = max_chars
                content_truncated = True
                break
            sections.append(section)
            used_chars += separator_chars + len(section)
        if len(sheet_names) > max_sheets and used_chars < max_chars:
            marker = f'[Workbook truncated after {max_sheets} sheets.]'
            separator_chars = 2 if sections else 0
            remaining = max_chars - used_chars - separator_chars
            if len(marker) <= remaining:
                sections.append(marker)
            else:
                content_truncated = True

    body = '\n\n'.join(sections)
    if content_truncated:
        body += f'\n\n[Attachment truncated after {max_chars} characters.]'
    _log_parse_done(file_path, kind='spreadsheet', started_at=started_at, body=body)
    return body


def extract_image_description(
    file_path: str,
    *,
    priority: int = 0,
    instruction: Optional[str] = None,
) -> str:
    if not is_model_role_available('vlm'):
        raise RuntimeError('vlm model role is not configured')
    started_at = _log_parse_start(file_path, kind='image')
    prompt_instruction = (instruction or VISION_EXTRACT_DEFAULT_INSTRUCTION).strip()
    encoded_query = encode_query_with_filepaths(prompt_instruction, [file_path])
    vlm = AutoModel(model='vlm')
    out = vlm(
        encoded_query,
        stream_output=False,
        llm_chat_history=[],
        lazyllm_files=None,
        priority=priority,
    )
    body = str(out).strip()
    _log_parse_done(file_path, kind='image', started_at=started_at, body=body)
    return body


def parse_attachment_content(file_path: str, *, priority: int = 0) -> str:
    """Parse one chat attachment via VLM, OCR, spreadsheet, or text readers."""
    path = str(Path(file_path).resolve())
    if not is_chat_attachment_file(path):
        raise ValueError(
            f'Unsupported attachment type: {Path(path).suffix or "(no extension)"}. '
            f'Supported: {_SUPPORTED_ATTACHMENT_LABEL}.'
        )
    if is_chat_image_file(path):
        if not is_model_role_available('vlm'):
            raise RuntimeError('vlm model role is not configured')
        return extract_image_description(path, priority=priority)
    if _suffix(path) in _DELIMITED_TEXT_EXTENSIONS:
        return read_chat_delimited_file(path)
    if is_chat_text_file(path):
        return read_chat_text_file(path)
    if is_chat_spreadsheet_file(path):
        return read_chat_spreadsheet_file(path)
    return read_chat_document_text(path)


def _build_reference_section(file_path: str, body: str, *, kind: str) -> str:
    name = Path(file_path).name
    label = {'image': 'Image', 'spreadsheet': 'Spreadsheet'}.get(kind, 'Document')
    safe_body = _sanitize_for_prompt_template(body.strip())
    return (
        f'## Attached {label} Reference: {name}\n'
        f'Source path: {file_path}\n\n'
        f'{safe_body}'
    )


def build_attachment_reference_prompt(files: List[str], *, priority: int = 0) -> str:
    sections: List[str] = []
    batch_started_at = time.perf_counter()
    for file_path in files:
        path = str(Path(file_path).resolve())
        try:
            if is_chat_image_file(path) and not is_model_role_available('vlm'):
                LOG.warning(f'[AttachmentReader] skip image (no vlm): {path}')
                continue
            if not is_chat_attachment_file(path):
                LOG.info(f'[AttachmentReader] unsupported attachment skipped: {path}')
                continue
            body = parse_attachment_content(path, priority=priority)
            if body:
                kind = 'image' if is_chat_image_file(path) else (
                    'spreadsheet' if is_chat_spreadsheet_file(path) else 'document'
                )
                sections.append(_build_reference_section(path, body, kind=kind))
        except Exception as exc:
            LOG.warning(f'[AttachmentReader] failed to parse {path}: {exc}')
    batch_elapsed = time.perf_counter() - batch_started_at
    LOG.info(
        f'[AttachmentReader] batch done files={len(files)} sections={len(sections)} '
        f'elapsed={batch_elapsed:.3f}s'
    )
    if not sections:
        return ''
    header = (
        '# Attached File References\n'
        'The following content was extracted from user-attached files for this turn. '
        'Use it directly when answering; do not ask the user to re-upload or paste file contents.'
    )
    return header + '\n\n' + '\n\n'.join(sections)

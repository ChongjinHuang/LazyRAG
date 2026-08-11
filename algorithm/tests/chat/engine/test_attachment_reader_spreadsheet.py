import pandas as pd

from lazymind.chat.engine.attachment_reader import (
    is_chat_attachment_file,
    is_chat_spreadsheet_file,
    parse_attachment_content,
    read_chat_delimited_file,
    read_chat_spreadsheet_file,
)


def _write_workbook(path):
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        pd.DataFrame({
            'month': ['2026-01', '2026-02', '2026-03'],
            'revenue': [120000, 138000, 151000],
            'profit': [24000, 30360, 34730],
        }).to_excel(writer, sheet_name='Sales', index=False)
        pd.DataFrame({
            'region': ['East', 'South'],
            'revenue': [241000, 168000],
        }).to_excel(writer, sheet_name='Regions', index=False)


def test_parse_xlsx_extracts_all_sheets_as_csv(tmp_path):
    workbook = tmp_path / 'quarterly-report.xlsx'
    _write_workbook(workbook)

    assert is_chat_attachment_file(str(workbook))
    assert is_chat_spreadsheet_file(str(workbook))

    content = parse_attachment_content(str(workbook))

    assert '## Sheet: Sales' in content
    assert 'month,revenue,profit' in content
    assert '2026-03,151000,34730' in content
    assert '## Deterministic Numeric Summary: Sales' in content
    assert 'revenue,3,409000' in content
    assert 'profit,3,89090' in content
    assert '## Sheet: Regions' in content
    assert 'East,241000' in content


def test_spreadsheet_reader_reports_row_and_sheet_truncation(tmp_path):
    workbook = tmp_path / 'quarterly-report.xlsx'
    _write_workbook(workbook)

    content = read_chat_spreadsheet_file(
        str(workbook),
        max_rows_per_sheet=1,
        max_sheets=1,
    )

    assert '2026-01,120000,24000' in content
    assert '2026-02' not in content
    assert '[Sheet truncated after 1 data rows.]' in content
    assert '[Workbook truncated after 1 sheets.]' in content


def test_delimited_reader_includes_deterministic_numeric_summary(tmp_path):
    report = tmp_path / 'report.csv'
    report.write_text(
        'month,revenue,profit\n2026-01,120000,24000\n2026-02,138000,30360\n',
        encoding='utf-8',
    )

    content = read_chat_delimited_file(str(report))

    assert '## Deterministic Numeric Summary: report.csv' in content
    assert 'revenue,2,258000,129000,120000,138000' in content
    assert 'profit,2,54360,27180,24000,30360' in content
    assert '## Data' in content
    assert '2026-02,138000,30360' in content

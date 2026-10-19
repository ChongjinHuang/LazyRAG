#!/usr/bin/env python3
"""Validate a diagram with the shipped self-check before atomically writing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from self_check import verify


def prepare(output, html):
    target = Path(output)
    if not target.is_absolute() or target.suffix.lower() != '.html' or not target.parent.is_dir():
        raise ValueError('output must be an absolute .html path in an existing conversation workspace directory')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.diagram-', suffix='.html', delete=False) as file:
            temporary = Path(file.name)
            file.write(html)
        errors = verify(temporary)
        if errors:
            return {'status': 'invalid', 'errors': errors}
        os.replace(temporary, target)
        data = target.read_bytes()
        return {'status': 'ok', 'validated': True, 'path': str(target),
                'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--html', required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.output, args.html)
    except (OSError, UnicodeError, ValueError) as error:
        result = {'status': 'invalid', 'errors': [str(error)]}
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())

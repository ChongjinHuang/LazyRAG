#!/usr/bin/env python3
"""Read-only Diagram Design marker/profile resolution with a compact token result."""
import argparse
import json
from pathlib import Path
import re

MARKER = re.compile(r'[ \t]*profile:[ \t]*([a-z0-9][a-z0-9-]{0,63})[ \t]*(?:\r?\n)?\Z')


class StyleError(ValueError):
    pass


def section(text, heading):
    match = re.search(r'^(' + re.escape(heading) + r')[ \t]*\r?\n(.*?)(?=^#{1,'
                      + str(len(heading.split(' ')[0])) + r'} |\Z)', text, re.M | re.S)
    return match.group(2).strip() if match else ''


def table(text, heading):
    body = section(text, heading)
    rows = {}
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        key = re.match(r'^`([^`]+)`(?:[ ]*\([^)]*\))?$', cells[0]) if cells else None
        if line.lstrip().startswith('|') and key:
            rows[key.group(1)] = cells[1:]
    return rows


def resolve(project_root, skill_root=None):
    project = Path(project_root)
    if not project.is_absolute() or not project.is_dir():
        raise StyleError('project-root must be an existing absolute directory from the workspace listing')
    root = Path(skill_root) if skill_root else Path(__file__).resolve().parents[1]
    defaults = (root / 'references/style-defaults.md').read_text(encoding='utf-8')
    working = root / 'references/style-guide.md'
    library = Path.home() / '.diagram-design/profiles'
    marker = project / '.diagram-design'
    warnings = []
    slug = None
    source = working
    if marker.exists():
        if not marker.is_file() or marker.is_symlink():
            warnings.append('Invalid .diagram-design marker: expected a regular non-symlink file; using working guide')
        else:
            match = MARKER.fullmatch(marker.read_text(encoding='utf-8'))
            if not match:
                warnings.append('Invalid .diagram-design marker: expected exactly profile: <valid-slug>; using working guide')
            else:
                slug = match.group(1)
                source = library / (slug + '.md')
                if slug == 'default' and not source.exists():
                    source = root / 'references/style-defaults.md'
                elif not source.is_file():
                    raise StyleError('Profile ' + slug + ' is missing; ask which profile to use (offer list). Do not fall back.')
                elif not source.resolve().is_relative_to(library.resolve()):
                    raise StyleError('Profile resolves outside the profile library; ask for a valid profile')
    text = source.read_text(encoding='utf-8')
    tokens = {}
    for key, heading in (('semantic_roles', '### Semantic roles'), ('typography', '## Typography')):
        required = table(defaults, heading)
        selected = table(text, heading)
        if not required or not selected:
            raise StyleError('Selected guide has missing or malformed ' + heading + '; ask whether to repair from defaults')
        missing = required.keys() - selected.keys()
        for name in sorted(missing):
            selected[name] = required[name]
        if missing:
            warnings.append('Backfilled ' + ', '.join(sorted(missing)) + ' in memory only; offer update to persist')
        tokens[key] = selected
    if slug is None:
        header = re.match(r'<!-- diagram-design-profile\s*\n(.*?)-->\s*\n', text, re.S)
        found = re.search(r'^slug: ([a-z0-9][a-z0-9-]{0,63})$', header.group(1), re.M) if header else None
        if found:
            slug = found.group(1)
            if not (library / (slug + '.md')).is_file():
                warnings.append('Working guide profile library entry is missing; guide remains usable, offer save')
        else:
            pristine = all(tokens[key] == table(defaults, heading) for key, heading in
                           (('semantic_roles', '### Semantic roles'), ('typography', '## Typography')))
            slug = 'default' if pristine else 'custom-unsaved'
    tokens['node_treatments'] = table(text, '## Node type → treatment') or table(defaults, '## Node type → treatment')
    return {'status': 'ok', 'profile': slug, 'source': str(source), 'marker_found': marker.exists(),
            'warnings': warnings, **tokens}, text, defaults


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--details', choices=('series', 'terminal', 'cjk'), action='append', default=[])
    args = parser.parse_args()
    try:
        result, text, defaults = resolve(args.project_root)
        headings = {'series': ['### Series palette (multi-series chart types only)'],
                    'terminal': ['### Terminal skin (opt-in alternate)'],
                    'cjk': ['### Korean labels', '### Traditional Chinese labels', '### Font stack']}
        for detail in args.details:
            result[detail] = {h: section(text, h) or section(defaults, h) for h in headings[detail]}
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        return 0
    except (StyleError, OSError, UnicodeError) as error:
        print(json.dumps({'status': 'needs_input', 'message': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

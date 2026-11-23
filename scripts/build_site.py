#!/usr/bin/env python3
"""Project the entire pinned publisher portal as an OKF 0.3 source archive."""

from collections import Counter, defaultdict
import gzip
from hashlib import sha1
import json
from pathlib import Path
import zipfile

from bs4 import BeautifulSoup, NavigableString

from build import ROOT, SITE, build as build_case, digest, encode, markdown

PUBLIC = 'https://github.com/cyberdudeuk/ai-capability-governance'
LICENCE = 'CC-BY-4.0'
IGNORE = {'script', 'style', 'template', 'noscript'}
BLOCKS = {
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'th', 'td', 'dt', 'dd', 'summary',
    'figcaption', 'legend', 'label', 'button', 'option', 'pre', 'blockquote', 'caption',
}
ASSET_RULES = {'.js': 'MIT', '.css': 'MIT', '.woff2': 'OFL-1.1'}


def text(element):
    return ' '.join(element.stripped_strings)


def cell(value):
    return str(value).replace('|', r'\|').replace('\n', ' ')


def title_label(value):
    return value.replace('[', r'\[').replace(']', r'\]')


def site_export():
    manifest = json.loads((ROOT / 'source/site-snapshot.json').read_text())
    case_files, case_receipt = build_case()
    commit = manifest['commit']
    pinned = f'{PUBLIC}/blob/{commit}/index.html'
    files = {}
    index_data = None
    for record in manifest['deploy_files']:
        source = ROOT / 'source/snapshots' / record['snapshot']
        data = gzip.decompress(source.read_bytes())
        if digest(data) != record['sha256'] or len(data) != record['bytes']:
            raise ValueError(f'Archived source has changed: {record["path"]}')
        if record['path'] == 'index.html':
            index_data = data
        files[f'source-bytes/{record["path"]}.gz'] = source.read_bytes()
    if index_data is None or digest(index_data) != case_receipt['snapshot_sha256']:
        raise ValueError('The portal and the worked case must use the same HTML snapshot')

    code_licence = (ROOT / 'source/snapshots/em-code-LICENSE.txt').read_bytes()
    expected = next(row['sha'] for row in manifest['repository_files'] if row['path'] == 'LICENSE')
    blob = b'blob ' + str(len(code_licence)).encode() + b'\0' + code_licence
    if sha1(blob).hexdigest() != expected:
        raise ValueError('Publisher code licence differs from the pinned Git blob')
    files['source-bytes/em-code-LICENSE.txt'] = code_licence

    dom = BeautifulSoup(index_data, 'html.parser')
    elements = dom.find_all(True)
    element_ids = {id(element): i for i, element in enumerate(elements, 1)}
    sections = dom.select('section[id]')
    section_ids = {id(element): element['id'] for element in sections}
    groups = {'page-shell': 'Page shell and ungrouped content'}
    for section in sections:
        heading = section.find(['h1', 'h2', 'h3', 'h4'])
        groups[section['id']] = text(heading) if heading else section['id'].replace('-', ' ')
    if len(groups) != len(sections) + 1:
        raise ValueError('Section identifiers are ambiguous')

    rows = []
    section_blocks = defaultdict(list)
    links = []
    controls = []
    for element in elements:
        ancestors = list(element.parents)
        group = next((section_ids[id(e)] for e in [element, *ancestors] if id(e) in section_ids), 'page-shell')
        row = {
            'ordinal': element_ids[id(element)],
            'parent': element_ids.get(id(element.parent)),
            'tag': element.name,
            'section': group,
            'attributes': element.attrs,
        }
        if element.name not in IGNORE:
            value = ' '.join(
                str(s).strip() for s in element.children
                if type(s) is NavigableString and s.strip()
            )
            if value:
                row['direct_text'] = value
        rows.append(row)

        if any(ancestor.name in IGNORE for ancestor in ancestors):
            continue
        if element.name in BLOCKS and not any(
            ancestor.name in BLOCKS for ancestor in ancestors
        ):
            value = text(element)
            if value:
                section_blocks[group].append((row['ordinal'], element.name, value))
        if element.name == 'a' and element.has_attr('href'):
            links.append({'element': row['ordinal'], 'section': group, 'label': text(element),
                          'target': element['href']})
        if element.name in {'form', 'input', 'button', 'select', 'textarea', 'details', 'output', 'dialog'}:
            controls.append({'element': row['ordinal'], 'section': group, 'tag': element.name,
                             'label': text(element) if element.name == 'button' else element.get('aria-label', ''),
                             'id': element.get('id')})

    if len(rows) != len(elements) or set(row['section'] for row in rows) != groups.keys():
        raise ValueError('HTML element or section coverage differs from the source')
    counts = Counter(row['section'] for row in rows)
    files['evidence/dom-elements.jsonl'] = b''.join(
        (json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n').encode() for row in rows
    )
    files['evidence/links.json'] = encode(links)
    files['evidence/controls.json'] = encode(controls)
    asset_rows = []
    for row in manifest['deploy_files']:
        path = row['path']
        asset_rows.append({
            **row, 'archive_path': f'source-bytes/{path}.gz',
            'licence_context': ASSET_RULES.get(Path(path).suffix, 'Publisher content and notices; see bundle index'),
        })
    files['evidence/source-inventory.json'] = encode({**manifest, 'deploy_files': asset_rows})
    files['evidence/section-index.json'] = encode([
        {'id': key, 'title': label, 'elements': counts[key], 'text_blocks': len(section_blocks[key]),
         'source': SITE + ('' if key == 'page-shell' else '#' + key), 'concept': f'sections/{key}.md'}
        for key, label in groups.items()
    ])

    summary = [
        '# AI Capability Governance and Implementation', '',
        'An independent OKF 0.3 archive of Em’s public site at release 3.4.0. '
        'Each section has a readable text projection. The ordered element inventory and compressed original files '
        'preserve tables, controls, SVGs, runtime inputs and other details omitted from the readable projection.', '',
        f'Captured **{len(sections)} named sections**, **{len(rows):,} HTML elements**, '
        f'**{len(links):,} links** and **{len(controls):,} controls** from the main page, '
        f'plus **{len(asset_rows)} deployment files** from the pinned Git tree.', '',
        'Start with [the correspondence case](correspondence/index.md) for the curated OKF+ example. '
        'Its semantic relationships are supplied as YAML-LD and JSON-LD.', '',
        '## Read the site by section', '',
        '| Section | HTML elements | Text blocks |', '| --- | ---: | ---: |',
    ]
    for key, label in groups.items():
        link = SITE + ('' if key == 'page-shell' else '#' + key)
        blocks = section_blocks[key]
        summary.append(f'| [{title_label(cell(label))}](sections/{key}.md) | {counts[key]} | {len(blocks)} |')
        lines = [f'# {label}', '', f'[Open this section on the publisher’s website]({link})', '',
                 'The numbers in brackets identify elements in the ordered DOM inventory. '
                 'This is a text projection of Em’s material.', '']
        for number, tag, value in blocks:
            plain = value.replace('\n', ' ')
            if tag.startswith('h') and len(tag) == 2:
                lines += [f'## {plain} [{number}]', '']
            else:
                lines += [f'[{number}] {plain}', '']
        files[f'sections/{key}.md'] = markdown({
            'type': 'publisher-section', 'title': label, 'status': 'draft',
            'sources': [{'title': label, 'resource': link}],
            'x-dom-section': key,
        }, '\n'.join(lines))

    summary += ['', '## Source and scope', '',
                '- [Publisher code licence](source-bytes/em-code-LICENSE.txt)',
                '- [Content licence](https://creativecommons.org/licenses/by/4.0/)',
                f'- [Pinned publisher HTML]({pinned})',
                '- [Section index](evidence/section-index.json)',
                '- [Ordered HTML elements and attributes](evidence/dom-elements.jsonl)',
                '- [Link inventory](evidence/links.json)',
                '- [Control inventory](evidence/controls.json)',
                '- [Deployment and repository inventory with hashes](evidence/source-inventory.json)',
                '', 'The publisher’s content is CC BY 4.0 and code is MIT, with the included SIL Open Font License for fonts. '
                'This archive attributes Em, retains source links and records the extraction. '
                'Source files are compressed as data. External destinations are indexed as links. '
                'The Git inventory also identifies repository files outside the Pages deployment.', '',
                'The full static capture is separate from operational verification. '
                'The original site remains the reference for live calculators, dynamically assembled views and changing resources. '
                'The full corpus has not been independently semantically reviewed.']
    files['index.md'] = markdown({
        'okf_version': '0.3', 'title': 'AI Capability Governance and Implementation',
        'description': 'Pinned public publisher-site archive with a curated OKF+ correspondence case',
        'license': LICENCE,
        'x-upstream-commit': commit,
    }, '\n'.join(summary))
    files['log.md'] = b'# Bundle update log\n\n## 2026-11-23\n\n- Captured the complete declared Pages deployment and projected the main page sections.\n'
    for name, data in case_files.items():
        if name.startswith('bundle/'):
            files['correspondence/' + name.removeprefix('bundle/')] = data
    files['correspondence-visualisation.html'] = case_files['visualisation.html'].replace(
        b'bundle/', b'correspondence/'
    )

    receipt = {
        'commit': commit, 'html_sections': len(sections), 'section_concepts': len(groups),
        'html_elements': len(rows), 'text_blocks': sum(map(len, section_blocks.values())),
        'links': len(links), 'controls': len(controls), 'deploy_files': len(asset_rows),
        'deployed_files_verified': sum(x['live_observation']['status'] == 'exact' for x in asset_rows),
        'repository_files': len(manifest['repository_files']),
        'files': {name: digest(data) for name, data in sorted(files.items())},
    }
    return files, receipt


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    files, receipt = site_export()
    output = ROOT / 'generated'
    files['coverage-receipt.json'] = encode(receipt)
    for name, value in files.items():
        path = output / 'site-bundle' / name
        if args.check:
            if not path.is_file() or path.read_bytes() != value:
                raise SystemExit(f'Stale output: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)

    archive = output / 'okf-ai-capability-governance-full-site.zip'
    if args.check:
        with zipfile.ZipFile(archive) as stream:
            if set(stream.namelist()) != set(files) or any(
                stream.read(name) != value for name, value in files.items()
            ):
                raise SystemExit('Full-site ZIP bytes do not match the projection')
    else:
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
            for name, value in sorted(files.items()):
                entry = zipfile.ZipInfo(name, (2026, 11, 23, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                stream.writestr(entry, value)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()

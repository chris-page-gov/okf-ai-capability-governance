#!/usr/bin/env python3
"""Build the public Pages site and its exact-commit file inventory."""

import argparse
from html import escape
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
import yaml

from build import ROOT, SITE, digest, encode
from build_viz import build_viz
from build_explorer_companions import build as build_companions

OUTPUT = ROOT / '_site'
GENERATED = ROOT / 'generated'
ASSETS = ('index.html', 'site.css', 'favicon.png')
REPORTS = (
    'evaluation/BEGINNER-WALKTHROUGH.md', 'evaluation/CLIENT-EVALUATION.md',
    'evaluation/codex-response.md', 'evaluation/claude-response.txt',
    'evaluation/claude-full-site-response.txt', 'evaluation/copilot-response.txt',
    'evaluation/copilot-full-site-response.txt', 'evaluation/gemini-response.txt',
    'evaluation/skills/consume.md', 'evaluation/skills/generate.md',
    'evaluation/test-inputs.json', 'evidence/guarded-scan.json',
    'evidence/guarded-full-site-validate.json',
)


def local_target(route, value):
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        return None
    target = unquote(parts.path)
    if not target:
        return route
    if target.startswith('/'):
        raise ValueError(f'Subpath-unsafe link in {route}: {value}')
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(route), target))
    if resolved == '..' or resolved.startswith('../'):
        raise ValueError(f'Link leaves the site from {route}: {value}')
    return 'index.html' if resolved == '.' else resolved


def render_page(route, data, html_routes, markdown):
    text = data.decode()
    metadata = {}
    if text.startswith('---\n'):
        front_matter, divider, text = text.partition('\n---\n')
        if not divider:
            raise ValueError(f'Unclosed Markdown front matter: {route}')
        metadata = yaml.safe_load(front_matter[4:]) or {}
    heading = re.search(r'^# (.+)$', text, re.MULTILINE)
    title = escape(metadata.get('title') or (heading[1] if heading else PurePosixPath(route).stem))
    tokens = markdown.parse(text)
    for token in tokens:
        for item in token.children or []:
            if item.type != 'link_open':
                continue
            url = item.attrGet('href')
            target = local_target(route, url)
            if not target or target == route or not target.endswith('.md'):
                continue
            html_path = target.removesuffix('.md') + '.html'
            if html_path in html_routes:
                parts = urlsplit(url)
                item.attrSet('href', parts._replace(path=parts.path.removesuffix('.md') + '.html').geturl())
    content = markdown.renderer.render(tokens, markdown.options, {})
    if not heading:
        content = f'<h1>{title}</h1>\n' + content
    to_root = '../' * (len(PurePosixPath(route).parts) - 1)
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | AI capability governance</title>
<link rel="icon" href="{to_root}favicon.png">
<link rel="stylesheet" href="{to_root}site.css">
</head>
<body>
<header class="masthead"><div class="wrap top">
<a class="name" href="{to_root}index.html">AI capability governance</a>
<nav aria-label="Document"><a href="{escape(PurePosixPath(route).name)}">Read the Markdown</a>
<a href="{to_root}compare.html">Worked case</a></nav>
</div></header>
<main class="document">{content}</main>
</body>
</html>
""".encode()


def snapshot_files():
    """Read only named evaluation outputs and tracked screenshot files."""
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--', 'evaluation/captures'], cwd=ROOT
    ).decode().split('\0')
    captures = [
        name for name in names if re.fullmatch(r'evaluation/captures/[\w.-]+\.(png|jpg)', name)
    ]
    return {name: (ROOT / name).read_bytes() for name in (*REPORTS, *captures)}


def pages_config():
    contract = json.loads((ROOT / 'okf.publication.json').read_text())
    publication = contract['publication']
    targets = [target for target in publication['targets'] if target['kind'] == 'github-pages']
    if publication['mode'] != 'automatic-protected-main' or len(targets) != 1:
        raise ValueError('Pages target has not been declared in the publication contract')
    target = targets[0]
    if not target['exact_commit_required'] or not target['promote_without_rebuild']:
        raise ValueError('Pages must promote the exact validated candidate')
    return {
        'url': target['public_base_url'], 'branch': 'main',
        'workflow': target['workflow_path'], 'artifact': '_site/',
        'discovery': '.well-known/okf.json', 'manifest': 'publication.json',
        'standalone_reader': 'viz.html',
    }


def build():
    source = json.loads((ROOT / 'source/pilot.json').read_text())['source']
    base = pages_config()['url']
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    full = json.loads((GENERATED / 'site-bundle/coverage-receipt.json').read_text())
    pilot = json.loads((GENERATED / 'build-receipt.json').read_text())
    if full['commit'] != source['commit'] or pilot['core'] != '0.3':
        raise ValueError('Unexpected bundle source revision or core version')

    files = {name: (ROOT / 'source/pages' / name).read_bytes() for name in ASSETS}
    files.update(snapshot_files())
    for name, expected in full['files'].items():
        route = f'site-bundle/{name}'
        data = (GENERATED / route).read_bytes()
        if digest(data) != expected:
            raise ValueError(f'Site archive receipt mismatch: {route}')
        files[route] = data
    for route, expected in pilot['files'].items():
        data = (GENERATED / route).read_bytes()
        if digest(data) != expected:
            raise ValueError(f'Pilot receipt mismatch: {route}')
        files['compare.html' if route == 'visualisation.html' else route] = data
    for route, icon in (('compare.html', 'favicon.png'),
                        ('site-bundle/correspondence-visualisation.html', '../favicon.png')):
        link = f'<link rel="icon" href="{icon}">\n</head>'.encode()
        files[route] = files[route].replace(b'</head>', link, 1)
    inputs = json.loads(files['evaluation/test-inputs.json'])
    for name, expected in inputs['sha256'].items():
        route = f'downloads/{name}'
        data = (ROOT / route).read_bytes()
        if digest(data) != expected:
            raise ValueError(f'Evaluation input mismatch: {route}')
        files[route] = data
    for route in ('downloads/coverage-receipt.json', 'site-bundle/coverage-receipt.json'):
        files[route] = (ROOT / 'downloads/coverage-receipt.json').read_bytes()

    markdown = MarkdownIt('commonmark', {'html': False}).enable('table')
    readable = {route for route in files if route.endswith('.md')}
    html_routes = {route.removesuffix('.md') + '.html' for route in readable}
    for route in sorted(readable):
        files[route.removesuffix('.md') + '.html'] = render_page(route, files[route], html_routes, markdown)

    files['viz.html'] = build_viz(files, base, source, local_target)

    companions = build_companions()
    if overlap := files.keys() & companions.keys():
        raise ValueError(f'Explorer companions would replace canonical files: {sorted(overlap)}')
    files.update(companions)

    entrypoints = {
        'archive_index': 'site-bundle/index.md',
        'case_index': 'bundle/index.md',
        'json_ld': 'bundle/relationships.jsonld',
        'yaml_ld': 'bundle/relationships.yamlld',
        'case_evidence': 'bundle/evidence.json',
        'coverage': 'site-bundle/coverage-receipt.json',
        'full_bundle_zip': 'downloads/okf-ai-capability-governance-full-site.zip',
        'reading_copy': 'downloads/okf-pilot-reading-copy.txt',
        'visualisation': 'compare.html',
        'standalone_reader': 'viz.html',
        'walkthrough': 'evaluation/BEGINNER-WALKTHROUGH.html',
        'client_evaluation': 'evaluation/CLIENT-EVALUATION.html',
        'case_explorer': 'bundle/okf-explorer.json',
        'archive_explorer': 'site-bundle/okf-explorer.json',
        'case_walkthrough': 'bundle/walkthrough.html',
        'archive_walkthrough': 'site-bundle/walkthrough.html',
        'file_manifest': 'publication.json',
    }
    if set(entrypoints.values()) - files.keys() - {'publication.json'}:
        raise ValueError('A discovery entry point is missing')
    links = {key: urljoin(base, route) for key, route in entrypoints.items()}
    files['.well-known/okf.json'] = encode({
        'schema': 'okf-companion-discovery.v1', 'okf_version': '0.3',
        'semantic_profile': pilot['profile'], 'title': 'AI Capability Governance and Implementation',
        'status': 'draft-pilot', 'site': base, 'source_commit': commit,
        'publisher_source': {'name': source['publisher'], 'url': SITE, 'commit': source['commit'],
                             'release': source['release']},
        'entrypoints': links,
    })
    files['llms.txt'] = f"""# AI capability governance and implementation

> Independent OKF 0.3 site archive and draft OKF+ case adapted from Em’s published playbook.

- [Browse the standalone reader]({links['standalone_reader']})
- [Start with the correspondence case]({links['case_index']})
- [Check the supporting evidence]({links['case_evidence']})
- [Read machine relationships as JSON-LD]({links['json_ld']})
- [Read the full site archive index]({links['archive_index']})
- [Follow the correspondence question]({links['case_walkthrough']})
- [Follow the source archive question]({links['archive_walkthrough']})
- [Load the correspondence graph in Explorer]({links['case_explorer']})
- [Load the source archive in Explorer]({links['archive_explorer']})
- [Download the reading copy]({links['reading_copy']})
- [Browse machine discovery metadata]({urljoin(base, '.well-known/okf.json')})

The correspondence agent proposes replies in the worked case. The published send variant increases the tier and requires shadow mode while a person still commits the output. Local authorisation needs its own evidence and decision.
""".encode()
    files['publication.json'] = encode({
        'schema': 'okf-companion-pages-manifest.v1', 'source_commit': commit,
        'site': base, 'okf_version': pilot['core'], 'upstream_commit': source['commit'],
        'files': {name: digest(data) for name, data in sorted(files.items())},
    })

    for route, data in files.items():
        if not route.endswith('.html'):
            continue
        doc = BeautifulSoup(data, 'html.parser')
        for tag in doc.select('[href],[src]'):
            url = tag.get('href') or tag.get('src')
            if not url:
                continue
            target = local_target(route, url)
            if target and target not in files and f'{target}/index.html' not in files:
                raise ValueError(f'Missing local link from {route}: {url}')
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    files = build()
    existing = {p.relative_to(OUTPUT).as_posix() for p in OUTPUT.rglob('*') if p.is_file()}
    if extra := existing - files.keys():
        raise SystemExit(f'Unexpected files in _site: {sorted(extra)}')
    for name, data in files.items():
        target = OUTPUT / name
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                raise SystemExit(f'Incorrect site output: {name}')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print(f'Checked {len(files)} public Pages files.' if args.check else f'Built {len(files)} public Pages files.')


if __name__ == '__main__':
    main()

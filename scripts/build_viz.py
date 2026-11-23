"""Assemble a standalone reader from the already validated Pages inputs."""

import base64
from html import escape
import json
from pathlib import PurePosixPath
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
import yaml

from build import ROOT, SITE, encode


def as_data_url(path, content):
    mime = 'image/png' if path.endswith('.png') else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(content).decode('ascii')


def build_viz(files, base, source, local_target):
    graph = json.loads(files['bundle/relationships.jsonld'])['@graph']
    nodes = {row['@id']: 'bundle/' + row['route'] for row in graph if 'route' in row}
    relationships = [
        dict(row, key=row['@id'].rpartition(':')[-1]) for row in graph if 'source' in row
    ]
    root_edges = [row for row in relationships if row['source'] not in {r['target'] for r in relationships}]
    if len(root_edges) != 1 or len(relationships) < 2:
        raise ValueError('The worked case must have a single opening relationship')
    first = root_edges[0]
    controls = [row for row in relationships if row != first]
    if any(row['source'] != first['target'] for row in controls):
        raise ValueError('The worked case controls must describe the proposed action')
    for row in [first, *controls]:
        if row['source'] not in nodes or row['target'] not in nodes or len(row['evidence']) != 1:
            raise ValueError(f'Incomplete visualisation relationship {row["@id"]}')

    sections = json.loads(files['site-bundle/evidence/section-index.json'])
    groups = {
        'case': [*nodes.values(), 'bundle/index.md'],
        'archive': ['site-bundle/index.md', *(f'site-bundle/{row["concept"]}' for row in sections)],
        'walkthroughs': sorted(
            path for path in files
            if path.startswith('evaluation/') and path.endswith(('.md', '.txt', '.json'))
        ) + [
            'evidence/guarded-scan.json', 'evidence/guarded-full-site-validate.json',
        ],
    }
    html_to_document = {
        path.removesuffix('.md') + '.html' if path.endswith('.md') else path: path
        for paths in groups.values() for path in paths
    }
    html_to_document['site-bundle/correspondence/index.html'] = 'bundle/index.md'
    images = {}
    documents = []

    for group, paths in groups.items():
        for path in paths:
            raw = files[path].decode()
            metadata = {}
            if raw.startswith('---\n'):
                front_matter, divider, _ = raw.partition('\n---\n')
                if not divider:
                    raise ValueError(f'Incomplete front matter in {path}')
                metadata = yaml.safe_load(front_matter[4:]) or {}
            if path.endswith('.md'):
                rendered = path.removesuffix('.md') + '.html'
                doc = BeautifulSoup(files[rendered], 'html.parser').select_one('main')
                heading = doc.find('h1', recursive=False)
                title = heading.get_text(' ', strip=True) if heading else metadata['title']
                if heading:
                    heading.extract()
                for a in doc.select('[href]'):
                    href = a['href']
                    if href.startswith('#'):
                        continue
                    target = local_target(rendered, href)
                    if target in html_to_document:
                        a['href'] = '#document/' + quote(html_to_document[target], safe='')
                    elif target:
                        a['href'] = urljoin(base, target)
                for img in doc.select('img[src]'):
                    target = local_target(rendered, img['src'])
                    if target not in files or not target.endswith(('.png', '.jpg')):
                        raise ValueError(f'Unrecognised embedded screenshot in {path}: {img["src"]}')
                    images.setdefault(target, as_data_url(target, files[target]))
                    img['data-embedded'] = target
                    del img['src']
                body = doc.decode_contents()
                searchable = doc.get_text(' ', strip=True)
                kind = metadata.get('type') or ('Walkthrough' if group == 'walkthroughs' else 'Bundle index')
            else:
                title = PurePosixPath(path).stem.replace('-', ' ').capitalize()
                kind = 'Evidence receipt' if path.endswith('.json') else 'Recorded conversation'
                searchable = raw
                body = '<pre>' + escape(raw) + '</pre>'

            cited = metadata.get('sources') or []
            generated = metadata.get('generated') or {}
            documents.append({
                'path': path, 'view': group, 'title': title, 'kind': kind, 'body': body,
                'summary': metadata.get('description', ''),
                'status': metadata.get('status', ''),
                'verification': 'No verification recorded' if path in nodes.values() and not metadata.get('verified') else '',
                'generated': generated.get('at', ''),
                'reviewBy': metadata.get('stale_after', ''),
                'source': cited[0].get('resource', '') if cited else '',
                'search': ' '.join((title, path, kind, searchable)).lower(),
            })

    payload = encode({
        'okf_version': '0.3', 'nodes': nodes, 'relationships': [first, *controls],
        'documents': documents, 'images': images,
    }).decode().replace('<', '\\u003c')

    assets = ROOT / 'source/pages'
    template = (assets / 'viz.html').read_text()
    values = {
        'PAYLOAD': payload.rstrip(),
        'STYLE': (assets / 'viz.css').read_text().rstrip(),
        'SCRIPT': (assets / 'viz.js').read_text().rstrip(),
        'ICON': as_data_url('favicon.png', files['favicon.png']),
        'BUNDLE_URL': escape(urljoin(base, 'downloads/okf-ai-capability-governance-full-site.zip')),
        'UPSTREAM_RELEASE': escape(source['release']),
        'HOME_URL': escape(base),
        'SOURCE_URL': escape(SITE),
    }
    # Insert the payload last, so source text cannot be mistaken for a template token.
    for key, value in values.items():
        if key != 'PAYLOAD':
            template = template.replace(f'__{key}__', value)
    return template.replace('__PAYLOAD__', values['PAYLOAD'], 1).encode()

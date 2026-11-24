#!/usr/bin/env python3
"""Build source-bound OKF Explorer companions for both published scopes."""
from __future__ import annotations

import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import posixpath
import re
import textwrap
from urllib.parse import quote

import yaml

from build import ROOT, build as build_case, digest, encode
from build_site import SITE, site_export

READER_BASE = 'https://chris-page-gov.github.io/okf-explorer/explore/'
EXPECTED_SCOPES = {'full-site', 'correspondence'}
OUTPUT = ROOT / 'generated/explorer-companions'


def read_markdown(data: bytes, label: str) -> tuple[dict, str]:
    text = data.decode('utf-8')
    if not text.startswith('---\n'):
        raise ValueError(f'Missing YAML front matter: {label}')
    header, separator, body = text[4:].partition('\n---\n')
    if not separator:
        raise ValueError(f'Unclosed YAML front matter: {label}')
    frontmatter = yaml.safe_load(header)
    if not isinstance(frontmatter, dict) or not isinstance(frontmatter.get('type'), str):
        raise ValueError(f'Expected a typed Markdown concept: {label}')
    return frontmatter, body.rstrip() + '\n'


def load_walkthroughs() -> dict:
    value = json.loads((ROOT / 'source/walkthroughs.json').read_text())
    if value.get('schema') != 'okf-capability-governance-walkthroughs.v1':
        raise ValueError('Unsupported walkthrough source schema')
    if set(value.get('scopes', {})) != EXPECTED_SCOPES:
        raise ValueError('Walkthrough source must define the two existing bundle scopes')
    return value['scopes']


def descriptor_identity(scope: str, scope_url: str, source_commit: str,
                        nodes: dict, edges: list[dict]) -> dict:
    # Local annotations can change independently of the publisher's revision.
    material = {
        'okf_version': '0.3', 'semantic_profile': 'urn:okf:ai-capability-governance:profile:v1',
        'scope': scope, 'upstream_source_commit': source_commit, 'nodes': nodes, 'edges': edges,
    }
    canonical = (json.dumps(material, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':'), allow_nan=False) + '\n').encode()
    scope_snapshot = 'sha256:' + digest(canonical)
    return {
        'schema': 'okf-explorer-bundle.v0',
        'bundle_id': scope_url + 'okf-explorer.json',
        'version': '0.1.0',
        'snapshot_id': scope_snapshot,
        'okf_version': '0.3',
        'meta': {'title': 'AI capability governance — ' + scope.replace('-', ' '),
                 'status': 'review-candidate', 'scope': scope,
                 'upstream_source_commit': source_commit,
                 'snapshot_policy': 'canonical-source-nodes-and-qualified-edges-sha256'},
    }


def source_nodes(files: dict[str, bytes], prefix: str, concept_directory: str) -> dict[str, dict]:
    nodes = {}
    for path, data in sorted(files.items()):
        if not path.startswith(prefix + concept_directory + '/') or not path.endswith('.md'):
            continue
        route = path.removeprefix(prefix)
        frontmatter, body = read_markdown(data, path)
        nodes[route] = {
            **frontmatter,
            'id': route,
            'title': frontmatter['title'],
            'type': frontmatter['type'],
            'description': frontmatter.get('description', ''),
            'sources': frontmatter.get('sources', []),
            'section': Path(route).parts[0] if '/' in route else 'root',
            'source_path': route,
            'frontmatter': frontmatter,
            'body': body,
        }
    return nodes


def correspondence_edges(graph: dict, nodes: dict[str, dict]) -> list[dict]:
    route_by_iri = {
        node['frontmatter']['x-correspondence-iri']: route
        for route, node in nodes.items()
        if isinstance(node.get('frontmatter', {}).get('x-correspondence-iri'), str)
    }
    rows = graph.get('@graph')
    if not isinstance(rows, list):
        raise ValueError('The generated correspondence graph has no explicit @graph')
    assertions = [row for row in rows if isinstance(row, dict) and 'source' in row and 'predicate' in row and 'target' in row]
    if len(assertions) != 4:
        raise ValueError('Expected the four authored composite-case assertions')
    edges = []
    for assertion in assertions:
        source_iri = assertion['source']
        target_iri = assertion['target']
        source_route = route_by_iri.get(source_iri)
        target_route = route_by_iri.get(target_iri)
        if not source_route or not target_route:
            raise ValueError('A generated assertion endpoint has no Markdown source route')
        if assertion.get('assertion_scope') != 'synthetic-fixture' or assertion.get('authority', {}).get('class') != 'synthetic':
            raise ValueError('The companion must retain synthetic fixture qualifications')
        edges.append({
            'id': assertion['@id'],
            'assertion_id': assertion['@id'],
            'source': source_route,
            'target': target_route,
            'source_iri': source_iri,
            'target_iri': target_iri,
            'predicate': assertion['predicate'],
            'kind': assertion['kind'],
            'label': assertion['label'],
            'inverse_label': assertion['inverse_label'],
            'assertion_status': assertion['assertion_status'],
            'assertion_scope': assertion['assertion_scope'],
            'authority': assertion['authority'],
            'derivation': assertion['derivation'],
            'observed_at': assertion['observed_at'],
            'evidence': assertion['evidence'],
            'rights': assertion['rights'],
            'source_assertion': assertion,
        })
    return edges


def reader_url(bundle_url: str, title: str, route: str) -> str:
    return (f'{READER_BASE}?bundle={quote(bundle_url, safe="")}'
            f'&q={quote(title, safe="")}&view=reader#{quote(route, safe="/.")}')


def wrapped_lines(value: str, width: int) -> list[str]:
    return textwrap.wrap(str(value), width=width, break_long_words=False,
                         break_on_hyphens=False) or ['']


def svg_for(scope: str, source_commit: str, nodes: dict, edges: list[dict]) -> bytes:
    if scope == 'full-site':
        labels = [
            ('Pinned source', [f'Pages snapshot at {source_commit[:12]}']),
            ('Markdown projection', [f'{len(nodes)} typed section concepts;', '0 core graph assertions']),
            ('Deployment inventory', ['13 entries: 12 HTTP assets and', 'one empty .nojekyll marker']),
            ('Repository inventory', ['90 files counted separately from', 'the deployment set']),
            ('Boundary', ['Static capture; current dynamic', 'service behaviour is not established']),
        ]
        height = 175 + len(labels) * 165
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 {height}" role="img" aria-labelledby="title desc">',
                 '<title id="title">Scope of the pinned site archive</title>',
                 '<desc id="desc">Five evidence stages distinguish the pinned source, typed Markdown projection, deployment files, repository inventory and live-behaviour limitation.</desc>',
                 '<style>text{font-family:Arial,sans-serif;fill:#102a43}.box{fill:#f0f6fa;stroke:#176b87;stroke-width:3}.note{fill:#fff7e8;stroke:#8a5b00;stroke-width:3}.head{font-size:23px;font-weight:bold}.body{font-size:19px}.arrow{stroke:#486581;stroke-width:3;fill:none}</style>']
        for index, (heading, body_lines) in enumerate(labels):
            y = 18 + index * 165
            klass = 'note' if index == len(labels) - 1 else 'box'
            parts.append(f'<rect class="{klass}" x="20" y="{y}" width="520" height="132" rx="16"/>')
            parts.append(f'<text class="head" x="42" y="{y + 38}">{escape(heading)}</text>')
            for line_index, line in enumerate(body_lines):
                parts.append(f'<text class="body" x="42" y="{y + 76 + line_index * 24}">{escape(line)}</text>')
            if index < len(labels) - 1:
                parts.append(f'<path class="arrow" d="M280 {y + 132} V{y + 160}" marker-end="url(#arrow)"/>')
        parts.insert(3, '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#486581"/></marker></defs>')
        parts.append('</svg>')
        return ('\n'.join(parts) + '\n').encode()

    positions = {
        'concepts/mandate.md': 26,
        'concepts/send-variant.md': 255,
        'concepts/draft-only.md': 484,
        'concepts/shadow-mode.md': 713,
        'concepts/evidence-brief.md': 942,
    }
    card_height = 170
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 1240" role="img" aria-labelledby="title desc">',
             '<title id="title">The composite send-action case</title>',
             '<desc id="desc">The baseline mandate links to a send-action variant, which has three qualified synthetic-fixture links to draft-only, shadow-mode and review-evidence concepts.</desc>',
             '<defs><marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#486581"/></marker></defs>',
             '<style>text{font-family:Arial,sans-serif;fill:#102a43}.box{fill:#f0f6fa;stroke:#176b87;stroke-width:3}.note{fill:#fff7e8;stroke:#8a5b00;stroke-width:3}.head{font-size:22px;font-weight:bold}.body{font-size:19px}.edge{stroke:#486581;stroke-width:3;fill:none}.label{font-size:16px;font-weight:bold}</style>']
    for route, y in positions.items():
        node = nodes[route]
        title = node['title']
        klass = 'box' if route in {'concepts/mandate.md', 'concepts/send-variant.md'} else 'note'
        parts.append(f'<rect class="{klass}" data-route="{escape(route, quote=True)}" x="20" y="{y}" width="520" height="{card_height}" rx="16"/>')
        title_lines = wrapped_lines(title, 38)
        for line_index, line in enumerate(title_lines):
            parts.append(f'<text class="head" data-role="node-title" data-route="{escape(route, quote=True)}" x="40" y="{y + 37 + line_index * 25}">{escape(line)}</text>')
        if route == 'concepts/mandate.md':
            sub_lines = ['Tier 3 baseline; a caseworker commits', 'the action.']
        elif route == 'concepts/send-variant.md':
            sub_lines = ['Irreversible effect; Tier 4; L1 Draft only;', 'the example requires shadow mode.']
        else:
            sub_lines = [node.get('description', '')]
        if route not in {'concepts/mandate.md', 'concepts/send-variant.md'}:
            sub_lines = wrapped_lines(' '.join(sub_lines), 42)
        else:
            sub_lines = [part for source_line in sub_lines for part in wrapped_lines(source_line, 42)]
        body_y = y + 73 + (len(title_lines) - 1) * 25
        for line_index, line in enumerate(sub_lines):
            parts.append(f'<text class="body" data-role="node-body" data-route="{escape(route, quote=True)}" x="40" y="{body_y + line_index * 23}">{escape(line)}</text>')
    for edge in edges:
        source, target = edge['source'], edge['target']
        source_y = positions[source] + card_height
        target_y = positions[target]
        source_attribute = escape(source, quote=True)
        target_attribute = escape(target, quote=True)
        assertion_attribute = escape(edge['assertion_id'], quote=True)
        if source == 'concepts/mandate.md':
            path = f'M280 {source_y} V{target_y - 5}'
            label_x, label_y = 300, source_y + 35
        else:
            target_centre = target_y + card_height // 2
            path = f'M280 {source_y} H10 V{target_centre} H18'
            label_x, label_y = 40, target_y - 13
        parts.append(f'<path class="edge" data-source="{source_attribute}" data-target="{target_attribute}" data-assertion-id="{assertion_attribute}" d="{path}" marker-end="url(#arrow)"/>')
        for line_index, line in enumerate(wrapped_lines(edge['label'], 58)):
            parts.append(f'<text class="label" data-role="edge-label" data-assertion-id="{assertion_attribute}" x="{label_x}" y="{label_y + line_index * 18}">{escape(line)}</text>')
    for line_index, line in enumerate(wrapped_lines(
            'All four arrows are synthetic-fixture interpretations, not official mandates.', 60)):
        parts.append(f'<text class="body" data-role="disclaimer" x="20" y="{1170 + line_index * 20}">{escape(line)}</text>')
    parts.append('</svg>')
    return ('\n'.join(parts) + '\n').encode()


def html_for(scope: str, title: str, question: str, answer: str, limitations: list[str],
            sources: list[dict], diagram_alt: str, url: str) -> bytes:
    source_items = ''.join(
        f'<li><a href="{escape(item["href"], quote=True)}">{escape(item["label"])}</a>'
        f' <code>SHA-256 {escape(item["sha256"])}</code></li>' for item in sources
    )
    limitation_items = ''.join(f'<li>{escape(item)}</li>' for item in limitations)
    body = f'''<!doctype html>
<html lang="en-GB">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | AI capability governance</title>
<style>
body{{margin:0;background:#f4f7f9;color:#172b4d;font:18px/1.55 system-ui,sans-serif}}
main{{box-sizing:border-box;max-width:900px;margin:0 auto;padding:clamp(1rem,4vw,3rem);background:#fff}}
h1,h2{{line-height:1.2}}.tag{{font-size:.9rem;color:#425466}}.answer{{border-left:5px solid #176b87;padding:.5rem 1rem;background:#f0f6fa}}
figure{{margin:1rem 0}}img{{display:block;width:100%;height:auto}}a{{color:#075985}}code{{overflow-wrap:anywhere;font-size:.78em}}
@media(max-width:480px){{body{{font-size:16px}}main{{padding:1rem}}}}
</style></head>
<body><main>
<p class="tag">{escape(scope)} · OKF 0.3 · source-linked walkthrough</p>
<h1>{escape(title)}</h1>
<h2>Question</h2><p>{escape(question)}</p>
<h2>Worked answer</h2><p class="answer">{escape(answer)}</p>
<p><a data-reader-link="primary" href="{escape(url, quote=True)}">Open the primary source record in OKF Explorer</a></p>
<figure><img src="walkthrough.svg" alt="{escape(diagram_alt, quote=True)}"><figcaption>{escape(diagram_alt)} <a href="walkthrough.svg">Open diagram full size</a></figcaption></figure>
<h2>Limits and negative controls</h2><ul>{limitation_items}</ul>
<h2>Source material and hashes</h2><ul>{source_items}</ul>
</main></body></html>
'''
    return body.encode()


def journey_manifest(descriptor: dict, primary_route: str, primary_title: str,
                     nodes: dict[str, dict], edges: list[dict]) -> dict:
    routes = [primary_route]
    if edges:
        routes.extend(route for route in nodes if route not in routes)
    journeys = []
    for index, route in enumerate(routes):
        node = nodes[route]
        title = node['title']
        actions = [
            {'type': 'goto', 'hash': '#' + route,
             'params': {'q': title, 'view': 'reader'}},
            {'type': 'wait_for', 'selector': f'.right-panel h2:has-text("{title}")'},
        ]
        if node.get('status') == 'draft':
            actions.append({
                'type': 'wait_for',
                'selector': '.right-panel .badge[data-lifecycle-status="draft"]',
            })
        # Source links live in the Evidence tab; open it as a real user would
        # before asserting the source-card link below.
        actions.append({
            'type': 'click',
            'selector': '.right-panel [role="tab"]:text-is("Evidence")',
        })
        assertions = [
            {'type': 'text', 'selector': '.right-panel', 'includes': title},
            {'type': 'url_hash', 'equals': '#' + route},
            {'type': 'visible', 'selector': '.reader-view.shared-reader'},
            {'type': 'console_clean'},
        ]
        sources = node.get('sources', [])
        if sources and isinstance(sources[0], dict) and sources[0].get('resource'):
            source_url = sources[0]['resource']
            source_card_selector = f'.right-panel .small-node-links a[href="{source_url}"]'
            assertions.extend([
                {'type': 'visible', 'selector': source_card_selector},
                {
                    'type': 'attribute',
                    'selector': source_card_selector,
                    'name': 'href',
                    'equals': source_url,
                },
            ])
        journeys.append({
            'id': 'walkthrough-primary-record' if index == 0 else f'walkthrough-source-record-{index}',
            'actions': actions,
            'assertions': assertions,
        })
    return {
        'schema': 'okf-explorer-journeys.v1',
        'bundle_descriptor': 'okf-explorer.json',
        'expected_identity': {
            'schema': descriptor['schema'],
            'id': descriptor['bundle_id'],
            'version': descriptor['version'],
            'snapshot': descriptor['snapshot_id'],
        },
        'journeys': journeys,
    }


def make_scope(scope: str, config: dict, bundle_files: dict[str, bytes], graph: dict | None,
               source_commit: str, base_url: str, project_materials: dict[str, bytes]) -> dict[str, bytes]:
    scope_name = config['route_prefix']
    scope_url = base_url + scope_name + '/'
    descriptor_url = scope_url + 'okf-explorer.json'
    prefix = scope_name + '/'
    nodes = source_nodes(bundle_files, prefix, config['concept_directory'])
    if not nodes:
        raise ValueError(f'No typed Markdown source concepts for {scope}')
    primary_route = config['primary_route']
    if primary_route not in nodes:
        raise ValueError(f'Primary route is absent from the {scope} source concepts')
    primary_title = nodes[primary_route]['title']
    edges = correspondence_edges(graph, nodes) if graph else []
    identity = descriptor_identity(scope, scope_url, source_commit, nodes, edges)
    descriptor = {
        **identity,
        'title': identity['meta']['title'],
        'description': 'A bounded source projection for the accompanying worked question.',
        'nodes': nodes,
        'edges': edges,
    }
    descriptor_bytes = encode(descriptor)
    url = reader_url(descriptor_url, primary_title, primary_route)
    outputs = {
        prefix + 'okf-explorer.json': descriptor_bytes,
        prefix + 'walkthrough.svg': svg_for(scope, source_commit, nodes, edges),
    }
    source_copy = prefix + 'walkthrough-source.json'
    if source_copy in bundle_files:
        outputs[source_copy] = bundle_files[source_copy]
    materials = dict(project_materials)
    for path, data in bundle_files.items():
        if path in config['sources']:
            materials[path] = data
        if path.startswith(prefix + config['concept_directory'] + '/') and path.endswith('.md'):
            materials[path] = data
    materials[prefix + 'okf-explorer.json'] = descriptor_bytes
    primary_sources = nodes[primary_route].get('sources', [])
    primary_source_url = (
        primary_sources[0].get('resource')
        if primary_sources and isinstance(primary_sources[0], dict)
        else None
    )
    linked_sources = []
    for path in config['sources']:
        data = materials.get(path)
        if data is None:
            # Source manifests and snapshots are privately hash-bound, while the guide links
            # to their public, human-readable projections and source registers.
            continue
        local_route = posixpath.relpath(path, start=scope_name)
        label = Path(path).name
        if path.endswith('.gz'):
            label = 'Pinned original HTML snapshot (gzip)'
        linked_sources.append({'href': local_route, 'label': label, 'sha256': digest(data)})
    # Every document in the Reader projection is bound by path and SHA-256,
    # including source-only sections not listed as guide citations.
    source_documents = {
        path: digest(data) for path, data in sorted(bundle_files.items())
        if path.startswith(prefix + config['concept_directory'] + '/') and path.endswith('.md')
    }
    evidence = {
        'schema': 'okf-capability-governance-walkthrough-evidence.v1',
        'scope': scope,
        'bundle_descriptor': 'okf-explorer.json',
        'reader_url': url,
        'primary_route': primary_route,
        'primary_title': primary_title,
        'primary_source_url': primary_source_url,
        'question': config['question'],
        'answer': config['answer'],
        'limitations': config['limitations'],
        'negative_controls': config['negative_controls'],
        'source_commit': source_commit,
        'core_version': '0.3',
        'concept_count': len(nodes),
        'edge_count': len(edges),
        'assertion_ids': [edge['assertion_id'] for edge in edges],
        'source_documents': source_documents,
        'material_hashes': {path: digest(data) for path, data in sorted(materials.items())},
        'reader_manifest': prefix + 'walkthrough.explorer-journeys.json',
        'diagram': prefix + 'walkthrough.svg',
    }
    outputs[prefix + 'walkthrough-evidence.json'] = encode(evidence)
    outputs[prefix + 'walkthrough.explorer-journeys.json'] = encode(
        journey_manifest(descriptor, primary_route, primary_title, nodes, edges)
    )
    diagram_alt = ('A source snapshot flows to thirty section concepts, a separately counted deployment set and repository inventory, with current dynamic behaviour out of scope.'
                   if scope == 'full-site' else
                   'The baseline mandate links to the send-action variant, which links through three synthetic-fixture assertions to draft-only, shadow-mode and review-evidence concepts.')
    outputs[prefix + 'walkthrough.html'] = html_for(
        scope, identity['meta']['title'], config['question'], config['answer'], config['limitations'],
        linked_sources, diagram_alt, url
    )
    ai_context = [
        f'# {identity["meta"]["title"]}', '',
        f'Core version: OKF {identity["okf_version"]}. Bundle scope: `{scope}`.',
        f'Pinned source commit: `{source_commit}`.', '',
        '## Question', '', config['question'], '',
        '## Source-grounded answer', '', config['answer'], '',
        '## Limits', '', *[f'- {item}' for item in config['limitations']], '',
        '## Reader record', '', f'- Title: {primary_title}',
        f'- Route: `{primary_route}`', f'- Reader URL: {url}', '',
        '## Source material', '',
        *[f'- `{path}` — SHA-256 `{digest(data)}`' for path, data in sorted(materials.items())], '',
        'No model response or external API call is part of this generated context.', ''
    ]
    outputs[prefix + 'ai-context.md'] = '\n'.join(ai_context).encode()
    outputs[prefix + 'llms.txt'] = (
        f'# {identity["meta"]["title"]}\n\n'
        f'> Bounded OKF 0.3 source projection for the {scope} scope.\n\n'
        f'- [Open the worked question](walkthrough.html)\n'
        f'- [Open the primary Explorer record]({url})\n'
        f'- [Read the source-linked Reader context](ai-context.md)\n'
        f'- [Read the machine evidence](walkthrough-evidence.json)\n'
        f'- [Inspect the source descriptor](okf-explorer.json)\n'
    ).encode()
    return outputs


def build() -> dict[str, bytes]:
    scopes = load_walkthroughs()
    full_files, full_receipt = site_export()
    case_files, case_receipt = build_case()
    full_markdown = {f'site-bundle/{path}': data for path, data in full_files.items()}
    case_markdown = {path: data for path, data in case_files.items()}
    source_manifest_bytes = (ROOT / 'source/site-snapshot.json').read_bytes()
    pilot_source_bytes = (ROOT / 'source/pilot.json').read_bytes()
    full_markdown['site-bundle/walkthrough-source.json'] = source_manifest_bytes
    case_markdown['bundle/walkthrough-source.json'] = pilot_source_bytes
    source = json.loads((ROOT / 'source/pilot.json').read_text())['source']
    snapshot = json.loads((ROOT / 'source/site-snapshot.json').read_text())
    index_snapshot = next(row['sha256'] for row in snapshot['deploy_files'] if row['path'] == 'index.html')
    if full_receipt['commit'] != snapshot['commit'] or case_receipt['snapshot_sha256'] != index_snapshot:
        raise ValueError('The archive and correspondence case do not share the pinned source snapshot')
    if (full_receipt['section_concepts'] != 30 or full_receipt['deploy_files'] != 13
            or full_receipt['repository_files'] != 90
            or len([row for row in snapshot['deploy_files'] if row['path'] != '.nojekyll']) != 12):
        raise ValueError('The pinned archive counts differ from the walkthrough source')
    if len([path for path in full_markdown if re.fullmatch(r'site-bundle/sections/[^/]+\.md', path)]) != 30:
        raise ValueError('Expected exactly 30 typed source section concepts')
    correspondence_graph = json.loads(case_files['bundle/relationships.jsonld'])
    source_commit = snapshot['commit']
    project_materials = {
        'source/pilot.json': (ROOT / 'source/pilot.json').read_bytes(),
        'source/site-snapshot.json': (ROOT / 'source/site-snapshot.json').read_bytes(),
        'source/snapshots/em-index.html.gz': (ROOT / 'source/snapshots/em-index.html.gz').read_bytes(),
        'site-bundle/source-bytes/index.html.gz': full_files['source-bytes/index.html.gz'],
    }
    full_config = dict(scopes['full-site'], route_prefix='site-bundle', concept_directory='sections')
    case_config = dict(scopes['correspondence'], route_prefix='bundle', concept_directory='concepts')
    outputs = {}
    base_url = json.loads((ROOT / 'okf.publication.json').read_text())['publication']['targets'][0]['public_base_url']
    outputs.update(make_scope('full-site', full_config, full_markdown, None,
                              source_commit, base_url, project_materials))
    outputs.update(make_scope('correspondence', case_config, case_markdown, correspondence_graph,
                              source_commit, base_url, project_materials))
    canonical_routes = {f'site-bundle/{path}' for path in full_files} | set(case_files)
    collisions = set(outputs) & canonical_routes
    if collisions:
        raise ValueError(f'Companion paths collide with authored bundle files: {sorted(collisions)}')
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    outputs = build()
    for route, data in outputs.items():
        path = OUTPUT / route
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit(f'Stale generated companion: {route}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f'OKF 0.3 companions: {len(outputs)} generated routes across two source scopes')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Generate and verify the local OKF 0.3 correspondence pilot."""
from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import zipfile

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator, FormatChecker
from rdflib import Graph, RDF, URIRef
from rdflib.compare import isomorphic
import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = 'urn:okf:ai-capability-governance:'
SITE = 'https://cyberdudeuk.github.io/ai-capability-governance/'
PROFILE = BASE + 'profile:v1'
RDF_NS = str(RDF)
LICENSE = 'https://creativecommons.org/licenses/by/4.0/'


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def encode(data) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()


def evidence_records(config):
    snapshot = gzip.decompress((ROOT / 'source/snapshots/em-index.html.gz').read_bytes())
    if digest(snapshot) != config['snapshot_sha256']:
        raise ValueError('Pinned source snapshot digest mismatch')
    dom = BeautifulSoup(snapshot, 'html.parser')
    worked = dom.select_one('#ch-worked')
    variant = worked.find(string=lambda s: s and s.strip() == 'The agent sends the reply itself')
    reassessment = dom.select_one('#ch-raioperate').find(
        string=lambda s: s and s.strip() == 'New tools, actions, schedules or agent links.'
    )
    rows = {
        'baseline': ('#ch-worked', 'Worked example opening', worked.select_one('.pb-lede').get_text(' ', strip=True)),
        'send': ('#ch-worked', 'Variant where the agent sends its reply', variant.parent.parent.parent.get_text(' ', strip=True)),
        'reassessment': ('#ch-raioperate', 'Reassessment trigger for new actions', reassessment.parent.parent.get_text(' ', strip=True)),
    }
    for key, heading in (
        ('scope', 'In scope'), ('decision', 'Decision rights'), ('exclusions', 'Explicitly out of scope')
    ):
        element = worked.find('h5', string=heading).parent.find_next_sibling()
        rows[key] = ('#ch-worked', 'Mandate / ' + heading, element.get_text(' ', strip=True))
    permalink = 'https://github.com/cyberdudeuk/ai-capability-governance/blob/' + config['commit'] + '/index.html'
    records = {}
    for key, (anchor, locator, value) in rows.items():
        literal = ' '.join(value.split())
        records[key] = {
            '@id': BASE + 'evidence:' + key,
            'type': 'Pinned public source passage',
            'url': SITE + anchor,
            'resource': permalink,
            'source_artifact': 'source/snapshots/em-index.html.gz (uncompressed hash)',
            'source_sha256': config['snapshot_sha256'],
            'source_field': anchor,
            'locator': locator,
            'source_value': literal,
            'source_value_sha256': digest(literal.encode()),
            'source_value_hash_canonicalization': 'UTF-8; collapsed Unicode whitespace; trimmed',
            'retrieved_at': config['checked_at'],
        }
    checks = {'baseline': ['Tier 3'], 'send': ['Irreversible', 'Tier 4', 'Draft only', 'shadow mode'],
              'scope': ['draft a suggested reply'], 'decision': ['A caseworker commits']}
    for key, required in checks.items():
        if any(phrase not in records[key]['source_value'] for phrase in required):
            raise ValueError(f'Announced source wording changed at {key}')
    return records


def markdown(meta, body):
    return ('---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n' + body + '\n').encode()


def graph_document(concepts, edges, witnesses, config):
    context = {
        'label': 'http://www.w3.org/2000/01/rdf-schema#label',
        'source': {'@id': RDF_NS + 'subject', '@type': '@id'},
        'predicate': {'@id': RDF_NS + 'predicate', '@type': '@id'},
        'target': {'@id': RDF_NS + 'object', '@type': '@id'},
    }
    for key in ('route', 'kind', 'inverse_label', 'assertion_status', 'assertion_scope', 'observed_at'):
        context[key] = BASE + 'field:' + key
    for key in ('authority', 'evidence', 'rights'):
        context[key] = {'@id': BASE + 'field:' + key, '@type': '@json'}
    context['derivation'] = {'@id': BASE + 'field:derivation', '@type': '@id'}
    nodes = {
        key: {'@id': BASE + 'concept:' + key, 'label': item['title'], 'route': f'concepts/{key}.md'}
        for key, item in concepts.items()
    }
    validator = Draft202012Validator(
        json.loads((ROOT / 'profiles/semantic-assertion.schema.json').read_text()), format_checker=FormatChecker()
    )
    assertions = []
    ids = set()
    for edge in edges:
        origin, destination = nodes[edge['from']], nodes[edge['to']]
        evidence = witnesses[edge['witness']]
        predicate = BASE + 'predicate:' + edge['predicate']
        assertion = {
            '@id': BASE + 'assertion:' + edge['id'],
            '@type': [RDF_NS + 'Statement', BASE + 'type:QualifiedAssertion'],
            'source': origin['@id'],
            'predicate': predicate,
            'target': destination['@id'],
            'kind': 'case-relationship',
            'label': edge['label'],
            'inverse_label': edge['inverse_label'],
            'assertion_status': 'normalized',
            'assertion_scope': edge['scope'],
            'authority': {'class': 'synthetic', 'label': 'Published composite or pilot interpretation', 'source': evidence['url']},
            'derivation': BASE + 'method:curated-case-normalisation',
            'observed_at': config['checked_at'],
            'evidence': [evidence],
            'rights': {'source': LICENSE, 'assertion': 'CC-BY-4.0', 'attribution': config['publisher']},
        }
        validator.validate(assertion)
        if assertion['@id'] in ids:
            raise ValueError('Duplicate assertion ID')
        ids.add(assertion['@id'])
        origin.setdefault(predicate, []).append({'@id': destination['@id']})
        assertions.append(assertion)
    return {'@context': context, '@graph': [*nodes.values(), *assertions]}, assertions


def validate_graph(document, assertions):
    # All contexts are embedded and use only absolute identifiers.
    if not isinstance(document['@context'], dict):
        raise ValueError('Expected embedded context')
    encoded = encode(document)
    yld = yaml.safe_dump(document, allow_unicode=True, sort_keys=False).encode()
    first = Graph().parse(data=encoded, format='json-ld')
    second = Graph().parse(data=encode(yaml.safe_load(yld)), format='json-ld')
    if not isomorphic(first, second):
        raise ValueError('RDF graphs differ')
    for row in assertions:
        aid, source, predicate, target = map(URIRef, (row['@id'], row['source'], row['predicate'], row['target']))
        for triple in [(source, predicate, target), (aid, RDF.subject, source),
                       (aid, RDF.predicate, predicate), (aid, RDF.object, target)]:
            if triple not in first:
                raise ValueError(f'Missing relationship triple {triple}')
    return encoded, yld, len(first)


def build():
    config = json.loads((ROOT / 'source/pilot.json').read_text())
    source, concepts, edges = (config[k] for k in ('source', 'concepts', 'relationships'))
    witnesses = evidence_records(source)
    graph, assertions = graph_document(concepts, edges, witnesses, source)
    jsonld, yamld, triples = validate_graph(graph, assertions)
    files = {
        'bundle/relationships.jsonld': jsonld,
        'bundle/relationships.yamlld': yamld,
        'bundle/evidence.json': encode({'source': source, 'evidence': witnesses}),
    }
    intro = [
        '# Correspondence triage and the send action',
        '',
        'A local pilot adapted from Em’s public composite case. Use the index to find the mandate, '
        'compare the proposed send action and identify what a local reviewer would need. '
        'All concepts are drafts. The pilot’s review trigger follows the publisher’s portal review date.',
        '',
    ]
    for key, c in concepts.items():
        intro.append(f'- [{c["title"]}](concepts/{key}.md) — {c["description"]}')
        refs = c['sources']
        if set(re.findall(r'\[\^([^]]+)\]', c['body'])) != set(refs):
            raise ValueError(f'Unresolved source citation in {key}')
        fields = {
            'type': c['type'], 'title': c['title'], 'description': c['description'], 'status': 'draft',
            'generated': {'by': 'process:correspondence-pilot-export', 'at': source['checked_at']},
            'stale_after': source['check_again'],
            'sources': [{'id': eid, 'title': witnesses[eid]['locator'], 'resource': witnesses[eid]['url']}
                        for eid in refs],
            'x-correspondence-iri': BASE + 'concept:' + key,
        }
        related = [f'- [{concepts[e["to"]]["title"]}](./{e["to"]}.md)' for e in edges if e['from'] == key]
        notes = [f'[^{eid}]: {witnesses[eid]["locator"]}, Em’s public playbook.' for eid in refs]
        body = f'# {c["title"]}\n\n{c["body"]}'
        if related:
            body += '\n\n## Continue through the case\n\n' + '\n'.join(related)
        body += '\n\n' + '\n\n'.join(notes)
        files[f'bundle/concepts/{key}.md'] = markdown(fields, body)
    intro += ['', '## Provenance', '', f'Adapted from {source["publisher"]}, release {source["release"]}, '
              f'commit `{source["commit"]}`. Source extracts and the normalised graph are included.',
              '', f'- [Publisher’s worked example]({SITE}#ch-worked)',
              '- [Evidence register](evidence.json)', '- [Semantic graph](relationships.jsonld)']
    files['bundle/index.md'] = markdown({
        'okf_version': '0.3', 'title': 'Correspondence triage and the send action',
        'description': 'An independent draft export of one public agent-governance case.',
        'license': source['licence'],
        'x-correspondence-profile': PROFILE,
    }, '\n'.join(intro))
    files['bundle/log.md'] = (
        '# Bundle update log\n\n## 2026-11-23\n\n- Created the correspondence pilot from the pinned public source.\n'
    ).encode()
    visual_data = {
        'concepts': {key: {f: c[f] for f in ('title', 'description')} for key, c in concepts.items()},
        'edges': [{**e, 'evidence': a['evidence'][0], 'authority': a['authority']['label'],
                   'assertion': a['@id'], 'rights': a['rights']['source']} for e, a in zip(edges, assertions, strict=True)],
        'witnesses': witnesses,
    }
    template = (ROOT / 'source/visualisation.html').read_text()
    files['visualisation.html'] = template.replace('__PILOT_DATA__', encode(visual_data).decode().replace('<', '\\u003c')).encode()
    receipt = {'core': '0.3', 'profile': PROFILE, 'concepts': len(concepts), 'assertions': len(assertions),
               'triples': triples, 'snapshot_sha256': source['snapshot_sha256'],
               'files': {k: digest(v) for k, v in files.items()}}
    files['build-receipt.json'] = encode(receipt)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
        for key, data in sorted(files.items()):
            info = zipfile.ZipInfo(key, (2026, 11, 23, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, data)
    files['okf-ai-capability-governance-pilot.zip'] = archive.getvalue()
    return files, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    files, receipt = build()
    for name, data in files.items():
        p = ROOT / 'generated' / name
        if args.check:
            if not p.is_file() or p.read_bytes() != data:
                raise SystemExit(f'Stale generated output: {name}')
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
    print(f'OKF {receipt["core"]}: {receipt["concepts"]} concepts, {receipt["assertions"]} qualified assertions, {receipt["triples"]} matching RDF triples')


if __name__ == '__main__':
    main()

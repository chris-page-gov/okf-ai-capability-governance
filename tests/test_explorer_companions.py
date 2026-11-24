import copy
import json
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from build import build as build_case, digest
from build_site import site_export
from build_explorer_companions import build, descriptor_identity


def decoded(files, path):
    return json.loads(files[path])


class ExplorerCompanionTests(unittest.TestCase):
    def test_snapshot_changes_with_local_body_and_assertion_provenance(self):
        descriptor = decoded(build(), 'bundle/okf-explorer.json')
        nodes, edges = descriptor['nodes'], descriptor['edges']
        commit = descriptor['meta']['upstream_source_commit']
        scope_url = descriptor['bundle_id'].removesuffix('okf-explorer.json')
        def snapshot(candidate_nodes, candidate_edges):
            return descriptor_identity('correspondence', scope_url, commit, candidate_nodes, candidate_edges)['snapshot_id']
        baseline = snapshot(nodes, edges)
        self.assertRegex(baseline, r'^sha256:[0-9a-f]{64}$')
        changed_nodes = copy.deepcopy(nodes)
        changed_nodes['concepts/send-variant.md']['body'] += 'A separately reviewed local note.\n'
        self.assertNotEqual(snapshot(changed_nodes, edges), baseline)
        changed_edges = copy.deepcopy(edges)
        changed_edges[0]['observed_at'] = '2026-11-24T14:00:00Z'
        changed_edges[0]['source_assertion']['observed_at'] = '2026-11-24T14:00:00Z'
        self.assertNotEqual(snapshot(nodes, changed_edges), baseline)
        self.assertEqual(snapshot(dict(reversed(list(nodes.items()))), edges), baseline)

    def test_each_scope_has_its_own_exact_reader_identity_and_primary_link(self):
        files = build()
        for route_prefix, scope in (('site-bundle', 'full-site'), ('bundle', 'correspondence')):
            descriptor = decoded(files, f'{route_prefix}/okf-explorer.json')
            evidence = decoded(files, f'{route_prefix}/walkthrough-evidence.json')
            manifest = decoded(files, f'{route_prefix}/walkthrough.explorer-journeys.json')
            self.assertEqual(descriptor['schema'], 'okf-explorer-bundle.v0')
            self.assertEqual(descriptor['okf_version'], '0.3')
            self.assertEqual(descriptor['bundle_id'], parse_qs(urlsplit(evidence['reader_url']).query)['bundle'][0])
            self.assertEqual(evidence['scope'], scope)
            self.assertIn(evidence['primary_route'], descriptor['nodes'])
            self.assertEqual(evidence['primary_title'], descriptor['nodes'][evidence['primary_route']]['title'])
            parts = urlsplit(evidence['reader_url'])
            query = parse_qs(parts.query)
            self.assertEqual(parts.fragment, evidence['primary_route'])
            self.assertEqual(query['q'], [evidence['primary_title']])
            self.assertEqual(query['view'], ['reader'])
            self.assertEqual(manifest['expected_identity'], {
                'schema': descriptor['schema'], 'id': descriptor['bundle_id'],
                'version': descriptor['version'], 'snapshot': descriptor['snapshot_id'],
            })
            self.assertTrue(all('bundle' not in action.get('params', {})
                                for journey in manifest['journeys'] for action in journey['actions']))
            for journey in manifest['journeys']:
                goto = next(action for action in journey['actions'] if action['type'] == 'goto')
                self.assertEqual(goto['params']['view'], 'reader')
                self.assertIn({'type': 'visible', 'selector': '.reader-view.shared-reader'}, journey['assertions'])
                self.assertFalse(any(assertion.get('type') == 'url_param' and assertion.get('name') == 'view'
                                     for assertion in journey['assertions']))
            guide = files[f'{route_prefix}/walkthrough.html'].decode()
            document = BeautifulSoup(guide, 'html.parser')
            icon = document.select_one('head link[rel="icon"]')
            self.assertIsNotNone(icon)
            self.assertEqual(urljoin(descriptor['bundle_id'], icon['href']),
                             'https://chris-page-gov.github.io/okf-ai-capability-governance/favicon.png')
            primary_link = document.select_one('[data-reader-link="primary"]')
            self.assertIsNotNone(primary_link)
            self.assertEqual(primary_link['href'], evidence['reader_url'])
            diagram_link = BeautifulSoup(guide, 'html.parser').select_one('figure a[href="walkthrough.svg"]')
            self.assertIsNotNone(diagram_link)
            self.assertEqual(diagram_link.get_text(strip=True), 'Open diagram full size')
            self.assertIn('figure{margin:1rem 0}', guide)

    def test_full_site_keeps_concept_source_and_deployment_scopes_separate(self):
        files = build()
        descriptor = decoded(files, 'site-bundle/okf-explorer.json')
        evidence = decoded(files, 'site-bundle/walkthrough-evidence.json')
        self.assertEqual(len(descriptor['nodes']), 30)
        self.assertEqual(descriptor['edges'], [])
        self.assertEqual(evidence['concept_count'], 30)
        self.assertEqual(evidence['edge_count'], 0)
        self.assertEqual(len(evidence['source_documents']), 30)
        _, receipt = site_export()
        self.assertEqual(receipt['section_concepts'], 30)
        self.assertEqual(receipt['deploy_files'], 13)
        self.assertEqual(receipt['repository_files'], 90)
        raw_manifest = files['site-bundle/walkthrough-source.json']
        self.assertEqual(raw_manifest, Path('source/site-snapshot.json').read_bytes())
        self.assertEqual(digest(raw_manifest), evidence['material_hashes']['site-bundle/walkthrough-source.json'])
        self.assertIn('13 entries: 12 HTTP assets', files['site-bundle/walkthrough.svg'].decode())
        self.assertIn('current live behaviour', files['site-bundle/walkthrough-evidence.json'].decode())

    def test_reader_nodes_preserve_typed_markdown_fields_and_relative_source_paths(self):
        files = build()
        site_files, _ = site_export()
        case_files, _ = build_case()
        published = {
            'site-bundle': {f'site-bundle/{path}': data for path, data in site_files.items()},
            'bundle': case_files,
        }
        for prefix, content_dir in (('site-bundle', 'sections'), ('bundle', 'concepts')):
            descriptor = decoded(files, f'{prefix}/okf-explorer.json')
            base = f'https://chris-page-gov.github.io/ai-capability-governance/{prefix}/'
            self.assertEqual(len(descriptor['nodes']), 30 if prefix == 'site-bundle' else 5)
            for route, node in descriptor['nodes'].items():
                source_path = f'{prefix}/{content_dir}/{Path(route).name}'
                source_bytes = published[prefix][source_path]
                from build_explorer_companions import read_markdown
                frontmatter, body = read_markdown(source_bytes, source_path)
                self.assertEqual(node['source_path'], route)
                self.assertEqual(urljoin(base + 'okf-explorer.json', node['source_path']), base + route)
                self.assertEqual(node['frontmatter'], frontmatter)
                self.assertEqual(node['body'], body)
                for key, value in frontmatter.items():
                    self.assertEqual(node[key], value, f'{prefix} {route} lost frontmatter field {key}')
            manifest = decoded(files, f'{prefix}/walkthrough.explorer-journeys.json')
            expected_journeys = 1 if prefix == 'site-bundle' else 5
            self.assertEqual(len(manifest['journeys']), expected_journeys)
            for journey in manifest['journeys']:
                source_checks = [row for row in journey['assertions'] if row['type'] == 'attribute']
                self.assertEqual(len(source_checks), 1)
                self.assertEqual(source_checks[0]['name'], 'href')
                expected_source_card = source_checks[0]['selector']
                self.assertTrue(expected_source_card.startswith('.right-panel .small-node-links a[href="'))
                self.assertIn({'type': 'visible', 'selector': expected_source_card}, journey['assertions'])
                evidence_click = next((index for index, action in enumerate(journey['actions'])
                                       if action.get('type') == 'click'), None)
                title_wait = next(index for index, action in enumerate(journey['actions'])
                                  if action.get('type') == 'wait_for'
                                  and '.right-panel h2:has-text(' in action.get('selector', ''))
                self.assertIsNotNone(evidence_click)
                self.assertGreater(evidence_click, title_wait)
                self.assertEqual(journey['actions'][evidence_click]['selector'],
                                 '.right-panel [role="tab"]:text-is("Evidence")')

    def test_correspondence_svg_edges_match_the_qualified_graph_topology(self):
        files = build()
        descriptor = decoded(files, 'bundle/okf-explorer.json')
        xml = ElementTree.fromstring(files['bundle/walkthrough.svg'])
        namespace = '{http://www.w3.org/2000/svg}'
        actual = {
            (node.get('data-source'), node.get('data-target'), node.get('data-assertion-id'))
            for node in xml.findall(f'.//{namespace}path') if node.get('data-assertion-id')
        }
        expected = {
            (edge['source'], edge['target'], edge['assertion_id']) for edge in descriptor['edges']
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 4)
        branches = [path for path in xml.findall(f'.//{namespace}path')
                    if path.get('data-source') == 'concepts/send-variant.md']
        self.assertEqual(len(branches), 3)
        for path in branches:
            coords = re.fullmatch(r'M\d+ \d+ H(\d+) V\d+ H(\d+)', path.get('d', ''))
            self.assertIsNotNone(coords)
            trunk_x, endpoint_x = map(int, coords.groups())
            self.assertLess(trunk_x, 20)
            self.assertLess(endpoint_x, 20)
        marker = xml.find(f'.//{namespace}marker[@id="arrow"]')
        self.assertEqual(marker.get('markerUnits'), 'userSpaceOnUse')
        self.assertEqual(marker.get('markerWidth'), '10')
        self.assertEqual(marker.get('markerHeight'), '10')
        for text_node in xml.findall(f'.//{namespace}text[@data-role="node-body"]'):
            self.assertGreaterEqual(float(text_node.get('x')), 40)

    def test_correspondence_diagram_wraps_all_text_inside_cards_and_canvas(self):
        files = build()
        descriptor = decoded(files, 'bundle/okf-explorer.json')
        xml = ElementTree.fromstring(files['bundle/walkthrough.svg'])
        namespace = '{http://www.w3.org/2000/svg}'
        width, height = (int(value) for value in xml.get('viewBox').split()[2:])
        cards = {
            rect.get('data-route'): (float(rect.get('x')), float(rect.get('y')),
                                     float(rect.get('width')), float(rect.get('height')))
            for rect in xml.findall(f'.//{namespace}rect') if rect.get('data-route')
        }
        title_lines = {}
        body_lines = {}
        for element in xml.findall(f'.//{namespace}text'):
            role = element.get('data-role')
            value = ''.join(element.itertext())
            x, y = float(element.get('x')), float(element.get('y'))
            self.assertGreaterEqual(x, 0)
            self.assertLess(x, width)
            self.assertGreater(y, 0)
            self.assertLess(y, height)
            if role == 'node-title':
                self.assertLessEqual(len(value), 38)
                title_lines.setdefault(element.get('data-route'), []).append(value)
            elif role == 'node-body':
                self.assertLessEqual(len(value), 42)
                body_lines.setdefault(element.get('data-route'), []).append(value)
            elif role == 'edge-label':
                self.assertLessEqual(len(value), 58)
            elif role == 'disclaimer':
                self.assertLessEqual(len(value), 60)

        for route, node in descriptor['nodes'].items():
            x, y, card_width, card_height = cards[route]
            self.assertEqual(' '.join(title_lines[route]), node['title'])
            self.assertLessEqual(max(float(line.get('x')) for line in
                                     xml.findall(f'.//{namespace}text[@data-route="{route}"]')), x + card_width)
            self.assertTrue(all(float(line.get('y')) < y + card_height - 8
                                for line in xml.findall(f'.//{namespace}text[@data-route="{route}"]')))
            self.assertTrue(body_lines[route])
            if route == 'concepts/mandate.md':
                expected_body = 'Tier 3 baseline; a caseworker commits the action.'
            elif route == 'concepts/send-variant.md':
                expected_body = 'Irreversible effect; Tier 4; L1 Draft only; the example requires shadow mode.'
            else:
                expected_body = node['description']
            self.assertEqual(' '.join(body_lines[route]), expected_body)

        actual_labels = {}
        for element in xml.findall(f'.//{namespace}text[@data-role="edge-label"]'):
            actual_labels.setdefault(element.get('data-assertion-id'), []).append(''.join(element.itertext()))
        self.assertEqual(
            {edge['assertion_id']: ' '.join(actual_labels[edge['assertion_id']])
             for edge in descriptor['edges']},
            {edge['assertion_id']: edge['label'] for edge in descriptor['edges']},
        )

    def test_correspondence_view_preserves_all_synthetic_assertions_and_source_bytes(self):
        files = build()
        descriptor = decoded(files, 'bundle/okf-explorer.json')
        evidence = decoded(files, 'bundle/walkthrough-evidence.json')
        manifest = decoded(files, 'bundle/walkthrough.explorer-journeys.json')
        generated, _ = build_case()
        source_graph = json.loads(generated['bundle/relationships.jsonld'])
        original = [row for row in source_graph['@graph'] if 'source' in row and 'target' in row]
        self.assertEqual(len(descriptor['nodes']), 5)
        self.assertEqual(len(descriptor['edges']), 4)
        self.assertEqual(evidence['assertion_ids'], [row['@id'] for row in original])
        self.assertEqual([edge['source_assertion'] for edge in descriptor['edges']], original)
        self.assertTrue(all(edge['assertion_scope'] == 'synthetic-fixture' for edge in descriptor['edges']))
        self.assertTrue(all(edge['authority']['class'] == 'synthetic' for edge in descriptor['edges']))
        primary = manifest['journeys'][0]
        self.assertTrue(any(
            action.get('type') == 'wait_for'
            and action.get('selector') == '.right-panel .badge[data-lifecycle-status="draft"]'
            for action in primary['actions']
        ))
        self.assertEqual(files['bundle/walkthrough-source.json'], Path('source/pilot.json').read_bytes())
        answer = evidence['answer'].lower()
        self.assertIn('caseworker commits', answer)
        self.assertIn('local appointment', ' '.join(evidence['limitations']).lower())
        self.assertIn('official mandates', ' '.join(evidence['negative_controls']).lower())
        self.assertIn('Tier 4', files['bundle/walkthrough.svg'].decode())

    def test_material_hashes_bind_the_published_source_routes(self):
        files = build()
        source_site, _ = site_export()
        source_case, _ = build_case()
        published = {
            **{f'site-bundle/{path}': data for path, data in source_site.items()},
            **source_case,
            'site-bundle/walkthrough-source.json': Path('source/site-snapshot.json').read_bytes(),
            'bundle/walkthrough-source.json': Path('source/pilot.json').read_bytes(),
        }
        for scope in ('site-bundle', 'bundle'):
            evidence = decoded(files, f'{scope}/walkthrough-evidence.json')
            ai_context = files[f'{scope}/ai-context.md'].decode()
            for path, expected in evidence['source_documents'].items():
                self.assertEqual(digest(published[path]), expected)
                self.assertIn(f'`{path}`', ai_context)
            for path, expected in evidence['material_hashes'].items():
                if path in published:
                    self.assertEqual(digest(published[path]), expected)


if __name__ == '__main__':
    unittest.main()

"""Protect the publication boundary, frozen artefacts and independent gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import yaml
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('contracts', ROOT / 'scripts/check_contracts.py')
contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contracts)


class PublicationBoundaryTests(unittest.TestCase):
    def test_unclassified_changes_fail_even_with_documentation(self):
        contract = json.loads((ROOT / 'okf.publication.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'declared lifecycle boundary'):
            contracts.enforce_lockstep(contract, {'unreviewed.sh', 'README.md', 'CHANGELOG.md'})

    def test_controlled_change_requires_documentation_and_changelog(self):
        contract = json.loads((ROOT / 'okf.publication.json').read_bytes())
        for paths in [{'scripts/build.py'}, {'scripts/build.py', 'README.md'}]:
            with self.subTest(paths=paths), self.assertRaisesRegex(ValueError, 'documentation and changelog'):
                contracts.enforce_lockstep(contract, paths)
        controlled = contracts.enforce_lockstep(contract, {'scripts/build.py', 'README.md', 'CHANGELOG.md'})
        self.assertEqual(controlled, {'scripts/build.py'})

    def test_untrusted_commands_cannot_become_shell_actions(self):
        for command in (
            'uv run --locked python scripts/build.py; touch /tmp/untrusted',
            'uv run --locked python scripts/../outside.py',
            'uv run --locked python $(touch /tmp/untrusted)',
            'python scripts/build.py',
            'node scripts/browser.mjs | sh',
        ):
            with self.subTest(command=command), self.assertRaises(ValueError):
                contracts.command_path(command)

    def test_pinned_schema_rejects_legacy_unvalidated_lifecycle(self):
        with self.assertRaises(ValidationError):
            contracts.validator().validate({'schema': 'okf-publication.v1', 'publication': {'pages': {}}})

    def test_unreviewed_schema_bytes_are_rejected_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'profiles/publication-method/v1'
            directory.mkdir(parents=True)
            source = ROOT / 'profiles/publication-method/v1'
            for item in source.iterdir():
                (directory / item.name).write_bytes(item.read_bytes())
            schema = directory / 'repository-publication.schema.json'
            schema.write_bytes(schema.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'schema bytes changed'):
                contracts.validator(root)

    def test_both_independent_planes_are_required_before_deployment(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())
        jobs = workflow['jobs']
        self.assertEqual(set(jobs['validate']['needs']), {'core', 'browser'})
        self.assertEqual(jobs['validate']['if'], 'always()')
        step = jobs['validate']['steps'][0]
        self.assertEqual(step['run'], 'test "$CORE_RESULT" = success && test "$BROWSER_RESULT" = success')
        self.assertEqual(jobs['deploy']['needs'], 'validate')
        self.assertNotIn('continue-on-error', jobs['browser'])
        self.assertNotIn('if', jobs['browser'])

    def test_ci_reader_pin_matches_authored_consumer_identity(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/validate.yml').read_text())
        steps = workflow['jobs']['browser']['steps']
        checkout = next(step['with'] for step in steps if step.get('name') == 'Check out the reviewed Reader')
        consumer = json.loads((ROOT / 'source/explorer-consumer.json').read_bytes())
        self.assertEqual(checkout['ref'], consumer['commit'])
        self.assertEqual(checkout['repository'], 'chris-page-gov/okf-explorer')
        self.assertFalse(checkout['persist-credentials'])


if __name__ == '__main__':
    unittest.main()

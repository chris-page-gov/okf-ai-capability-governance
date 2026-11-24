#!/usr/bin/env python3
"""Validate the pinned lifecycle contract and its documented change scope."""
from __future__ import annotations

import argparse
from fnmatch import fnmatch
from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
import tomllib

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    'repository-publication.schema.json': '04c5d229a2900616d7a194d256ae1edb162d2c18beec7e2354723ce711b4eec3',
    'source-family.schema.json': '8c4734f554920fd34157ce90172a53ced492198d3761e7a62ebebf51036b3f6b',
}


def validator(root=ROOT):
    directory = root / 'profiles/publication-method/v1'
    lock = json.loads((directory / 'lock.json').read_bytes())
    if lock['files'] != SCHEMAS:
        raise ValueError('Publication schema lock differs from the reviewed pin')
    registry = Registry()
    documents = []
    for name, expected in SCHEMAS.items():
        raw = (directory / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError('Publication schema bytes changed: ' + name)
        document = json.loads(raw)
        Draft202012Validator.check_schema(document)
        documents.append(document)
        registry = registry.with_resource(document['$id'], Resource.from_contents(document))
    return Draft202012Validator(documents[0], registry=registry, format_checker=FormatChecker())


def command_path(command):
    if any(character in command for character in '\n;|&`$<>'):
        raise ValueError('Command declaration contains shell syntax')
    tokens = shlex.split(command)
    if tokens[:4] == ['uv', 'run', '--locked', 'python'] and len(tokens) >= 5:
        path = tokens[4]
    elif tokens[:1] == ['node'] and len(tokens) == 2:
        path = tokens[1]
    else:
        raise ValueError('Unreviewed command form')
    if not path.startswith('scripts/') or '..' in Path(path).parts or Path(path).is_absolute():
        raise ValueError('Command must name a local reviewed script')
    return path


def changed_files(base=None):
    if base:
        args = ['git', 'diff', '--name-only', base]
    else:
        args = ['git', 'diff', '--name-only', 'HEAD']
    tracked = subprocess.check_output(args, cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    return set(tracked + untracked)


def validate(root=ROOT):
    contract = json.loads((root / 'okf.publication.json').read_bytes())
    validator(root).validate(contract)
    semantic = json.loads((root / 'okf.semantic.json').read_bytes())
    if semantic['okf_core']['version'] != '0.3' or semantic['semantic_layer']['profile'] != 'urn:okf:ai-capability-governance:profile:v1':
        raise ValueError('Core or local semantic identity changed without a profile review')
    for declaration in contract['tooling']['commands']:
        path = root / command_path(declaration['command'])
        if path.is_symlink() or not path.is_file():
            raise ValueError('Declared script is missing or linked: ' + str(path.relative_to(root)))
    project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
    if project['requires-python'] != '==3.12.11' or (root / '.python-version').read_text().strip() != '3.12.11':
        raise ValueError('The governed Python version differs')
    normalise = lambda value: value.lower().replace('_', '-')
    requirements = {normalise(line.strip()) for line in (root / 'requirements.txt').read_text().splitlines() if line.strip()}
    if requirements != {normalise(item) for item in project['dependencies']}:
        raise ValueError('Locked project dependencies differ from the retained build requirements')
    return contract


def enforce_lockstep(contract, changed):
    policy = contract['lockstep']
    declared = [item['path'] for group in ('authored', 'generated')
                for item in contract['boundaries'][group]]
    unknown = sorted(path for path in changed
                     if not any(fnmatch(path, pattern) for pattern in declared))
    if unknown and policy['unknown_path_policy'] == 'fail-closed':
        raise ValueError('Changed paths need a declared lifecycle boundary: ' + ', '.join(unknown))
    controlled = {path for path in changed if any(fnmatch(path, pattern) for pattern in policy['controlled_paths'])}
    documentation = {path for path in changed if any(fnmatch(path, pattern) for pattern in policy['documentation_paths'])}
    if controlled and (not documentation or policy['changelog_path'] not in changed):
        raise ValueError('Controlled changes require documentation and changelog updates in the same change')
    return controlled


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', help='Git comparison base or range; command strings are never executed')
    args = parser.parse_args()
    contract = validate()
    changed = changed_files(args.base)
    controlled = enforce_lockstep(contract, changed)
    print(json.dumps({'schema': 'passed', 'semantic_identity': 'preserved', 'controlled_files': len(controlled), 'command_execution': 'none'}))


if __name__ == '__main__':
    main()

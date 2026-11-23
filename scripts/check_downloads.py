#!/usr/bin/env python3
"""Check the public downloads against the test record and a fresh build."""

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / 'generated'
DOWNLOADS = ROOT / 'downloads'


def compare_archives(public, rebuilt):
    # Compare member bytes so the check is independent of the zlib version.
    with ZipFile(public) as published, ZipFile(rebuilt) as generated:
        names = sorted(generated.namelist())
        if sorted(published.namelist()) != names:
            raise SystemExit(f'Archive inventory differs for {public.name}')
        for name in names:
            if published.read(name) != generated.read(name):
                raise SystemExit(f'Archive member differs: {public.name}/{name}')


def compare_files(public, rebuilt):
    if public.read_bytes() != rebuilt.read_bytes():
        raise SystemExit(f'File differs from the build: {public.relative_to(ROOT)}')


def main():
    record = json.loads((ROOT / 'evaluation/test-inputs.json').read_text())
    for name, expected in record['sha256'].items():
        public, rebuilt = DOWNLOADS / name, GENERATED / name
        if sha256(public.read_bytes()).hexdigest() != expected:
            raise SystemExit(f'Test input hash differs: {name}')
        if public.suffix == '.zip':
            compare_archives(public, rebuilt)
        else:
            compare_files(public, rebuilt)

    compare_files(DOWNLOADS / 'coverage-receipt.json', GENERATED / 'site-bundle/coverage-receipt.json')
    public, rebuilt = DOWNLOADS / 'correspondence', GENERATED / 'bundle'
    members = sorted(path.relative_to(rebuilt) for path in rebuilt.rglob('*') if path.is_file())
    if sorted(path.relative_to(public) for path in public.rglob('*') if path.is_file()) != members:
        raise SystemExit('Published correspondence tree differs from the build')
    for name in members:
        compare_files(public / name, rebuilt / name)

    print('Public downloads match the test inputs and rebuilt contents.')


if __name__ == '__main__':
    main()

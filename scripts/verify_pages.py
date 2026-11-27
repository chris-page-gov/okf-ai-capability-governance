#!/usr/bin/env python3
"""Verify the deployed Pages inventory against the validated candidate."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import file_digest, sha256
import json
from pathlib import Path, PurePosixPath
from time import sleep
from urllib.error import URLError
from urllib.parse import quote, urljoin
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(url):
    with urlopen(url, timeout=15) as response:
        if response.geturl() != url or response.status != 200:
            raise ValueError(f'Unexpected Pages response for {url}: {response.geturl()}')
        return response.read(), response.headers.get_content_type()


def check_file(base, item):
    path, expected = item
    parts = PurePosixPath(path)
    if parts.is_absolute() or '..' in parts.parts:
        raise ValueError(f'Unsafe Pages manifest path: {path}')
    body, content_type = fetch(urljoin(base, quote(path)))
    if sha256(body).hexdigest() != expected:
        raise ValueError(f'Live file differs from candidate: {path}')
    mime_types = {'.html': 'text/html', '.css': 'text/css', '.json': 'application/json'}
    expected_mime = mime_types.get(parts.suffix)
    if expected_mime and content_type != expected_mime:
        raise ValueError(f'Unexpected {content_type} for {path}')


def checked_manifest(body, commit, manifest_sha256, base):
    if sha256(body).hexdigest() != manifest_sha256:
        raise ValueError('Pages is serving a different manifest')
    manifest = json.loads(body)
    if not isinstance(manifest, dict) or (
        manifest.get('schema') != 'okf-companion-pages-manifest.v1'
        or manifest.get('source_commit') != commit
        or manifest.get('site') != base
        or manifest.get('okf_version') != '0.3'
    ):
        raise ValueError('Deployment identity differs from the candidate')
    if not isinstance(manifest.get('files'), dict) or 'index.html' not in manifest['files']:
        raise ValueError('Pages manifest has no landing page inventory')
    return manifest


def verify_candidate(candidate, commit, manifest_sha256, base):
    manifest_path = candidate / 'publication.json'
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('The local Pages publication manifest is missing or invalid')
    manifest = checked_manifest(manifest_path.read_bytes(), commit, manifest_sha256, base)
    files = set()
    for member in candidate.rglob('*'):
        if member.is_symlink():
            raise ValueError('The local Pages candidate contains a symbolic link')
        if member.is_file() and member != manifest_path:
            files.add(member.relative_to(candidate).as_posix())
    if files != manifest['files'].keys():
        raise ValueError('The local Pages file inventory differs from the manifest')
    for relative, expected in manifest['files'].items():
        with (candidate / relative).open('rb') as stream:
            if file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError(f'Local file differs from candidate: {relative}')
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--candidate', type=Path, help='Verify a local Pages package without network access')
    args = parser.parse_args()

    contract = json.loads((ROOT / 'okf.publication.json').read_text())
    publication = contract['publication']
    targets = [target for target in publication['targets'] if target['kind'] == 'github-pages']
    if publication['mode'] != 'automatic-protected-main' or len(targets) != 1:
        raise ValueError('Exactly one governed Pages target is required')
    target = targets[0]
    if not target['exact_commit_required'] or not target['promote_without_rebuild']:
        raise ValueError('Pages must promote the exact validated candidate')
    base = target['public_base_url']
    if args.candidate is not None:
        count = verify_candidate(args.candidate, args.commit, args.manifest_sha256, base)
        print(f'Verified {count} local Pages files at {args.commit}.')
        return
    for attempt in range(12):
        try:
            body, content_type = fetch(urljoin(base, 'publication.json'))
            if content_type != 'application/json':
                raise ValueError('Pages is serving a different manifest')
            manifest = checked_manifest(body, args.commit, args.manifest_sha256, base)
            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(lambda item: check_file(base, item), manifest['files'].items()))
            if sha256(fetch(base)[0]).hexdigest() != manifest['files']['index.html']:
                raise ValueError('Pages root differs from the built landing page')
            break
        except (ValueError, URLError, TimeoutError) as error:
            if attempt == 11:
                raise SystemExit(f'Pages verification failed: {error}') from error
            print(f'Waiting for the candidate to be served: {error}', flush=True)
            sleep(5)
    print(f'Verified {len(manifest["files"])} live files at {args.commit} and the public landing route.')


if __name__ == '__main__':
    main()

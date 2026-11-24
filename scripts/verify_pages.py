#!/usr/bin/env python3
"""Verify the deployed Pages inventory against the validated candidate."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--manifest-sha256', required=True)
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
    for attempt in range(12):
        try:
            body, content_type = fetch(urljoin(base, 'publication.json'))
            if content_type != 'application/json' or sha256(body).hexdigest() != args.manifest_sha256:
                raise ValueError('Pages is serving a different manifest')
            manifest = json.loads(body)
            if manifest['source_commit'] != args.commit or manifest['site'] != base:
                raise ValueError('Deployment identity differs from the candidate')
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

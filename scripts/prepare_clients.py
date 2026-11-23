#!/usr/bin/env python3
"""Prepare the text reading copy and instruction-only client skill packages."""

from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'generated'
    bundle = output / 'bundle'
    inputs = [bundle / 'index.md', *sorted((bundle / 'concepts').glob('*.md')), bundle / 'evidence.json']
    reading_copy = output / 'okf-pilot-reading-copy.txt'
    with reading_copy.open('w', encoding='utf-8') as target:
        target.write('OKF 0.3 pilot reading copy. The file boundaries below reproduce the index, all concept files and evidence register.\n')
        for source in inputs:
            target.write(f'\n===== {source.relative_to(bundle)} =====\n')
            target.write(source.read_text(encoding='utf-8'))

    transparency = output / 'site-bundle/sections/transparency.md'
    (output / 'okf-pilot-site-spot-check.txt').write_text(
        reading_copy.read_text(encoding='utf-8') + '\n===== sections/transparency.md =====\n'
        + transparency.read_text(encoding='utf-8'), encoding='utf-8'
    )

    for source in sorted((ROOT / 'evaluation/skills').glob('*.md')):
        slug = f'okf-pilot-{source.stem}'
        destination = output / 'client-skills' / slug
        destination.mkdir(parents=True, exist_ok=True)
        content = source.read_bytes()
        (destination / 'SKILL.md').write_bytes(content)
        with ZipFile(destination.parent / f'{slug}-claude.zip', 'w', ZIP_DEFLATED) as archive:
            entry = ZipInfo(f'{slug}/SKILL.md', (2026, 11, 23, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, content)


if __name__ == '__main__':
    main()

# AI capability governance OKF+

An independent OKF 0.3 archive of Em’s *AI Capability Governance and Implementation* site, with a curated OKF+ case about a correspondence agent. It gives a reader or AI both the public context and a short, traceable path through the decision about sending replies.

## Open the pilot

1. Read the [illustrated beginner walkthrough](evaluation/BEGINNER-WALKTHROUGH.md) for the original website and the bundle.
2. Download the [full-site ZIP](downloads/okf-ai-capability-governance-full-site.zip). Extract it and open **index.md** for the sections and source inventory.
3. Open **correspondence-visualisation.html** from the extracted full-site ZIP in a browser. Choose **Draft replies** or **Propose sending replies**. Select a relationship to inspect its supporting source.
4. Use the [small correspondence ZIP](downloads/okf-ai-capability-governance-pilot.zip) or browse the [correspondence bundle index](downloads/correspondence/index.md) to explore the case by itself. The [client evaluation](evaluation/CLIENT-EVALUATION.md) explains how the archives were supplied to each AI.

The full-site bundle preserves the pinned static site and classifies external destinations as links. The browser’s live calculators and other interactive workflows remain on the publisher’s site. The five curated concepts cover the correspondence case only. [Em’s website](https://cyberdudeuk.github.io/ai-capability-governance/)

## Reproduce and check

From this repository, use Python 3.12.11 in a virtual environment.

```sh
python -m pip install -r requirements.txt
python scripts/build.py
python scripts/build_site.py
python scripts/prepare_clients.py
python scripts/check_downloads.py
```

The check matches public download hashes to the evaluation record and rebuilt contents to the published files. The guarded Codex checks used the reviewed Explorer tooling at commit d0c5ad26843dd0e5ab1e7f9357838719ae9c3f83.

- [scripts/build.py](scripts/build.py) creates the small bundle and visualisation and checks the qualified assertions and graph parity.
- [scripts/build_site.py](scripts/build_site.py) creates the full archive and verifies captured bytes, structure and site membership.
- [scripts/prepare_clients.py](scripts/prepare_clients.py) makes the text fallback and provider skill packages after both builds.
- [Semantic contract](okf.semantic.json), [publication contract](okf.publication.json) and [local profile](profiles/README.md) record the source boundaries.

The installed guarded Codex skills validated both bundle roots and scanned the curated correspondence bundle. The frozen Explorer Bundle Wiki v1 profile targets OKF 0.2. This independent 0.3 profile reuses its assertion schema with a local validator, so the profile claim is scoped to this repository. [Pinned OKF 0.3 specification](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/SPEC.md) · [Explorer standards register](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-standards.md) · [Machine register](https://github.com/chris-page-gov/okf-explorer/blob/main/registry/okf-standards.json)

This public repository hosts the draft pilot and its evaluation. A GitHub Actions validation check runs on pull requests and updates to main. [Repository status](REPOSITORY_STATUS.md) · [Licensing and attribution](LICENSE_DECISIONS.md)

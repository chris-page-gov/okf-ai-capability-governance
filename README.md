# AI capability governance OKF+

An independent OKF 0.3 archive of Em’s *AI Capability Governance and Implementation* site, with a curated OKF+ case about a correspondence agent. It gives a reader or AI both the public context and a short, traceable path through the decision about sending replies.

## Open the pilot

[Open the GitHub Pages companion](https://chris-page-gov.github.io/okf-ai-capability-governance/) · [OKF discovery descriptor](https://chris-page-gov.github.io/okf-ai-capability-governance/.well-known/okf.json)

1. Read the [illustrated beginner walkthrough](evaluation/BEGINNER-WALKTHROUGH.md) for the original website and the bundle.
2. Download the [full-site ZIP](downloads/okf-ai-capability-governance-full-site.zip). Extract it and open **index.md** for the sections and source inventory.
3. Open **correspondence-visualisation.html** from the extracted full-site ZIP in a browser. Choose **Draft replies** or **Propose sending replies**. Select a relationship to inspect its supporting source.
4. Use the [small correspondence ZIP](downloads/okf-ai-capability-governance-pilot.zip) or browse the [correspondence bundle index](downloads/correspondence/index.md) to explore the case by itself. The [client evaluation](evaluation/CLIENT-EVALUATION.md) explains how the archives were supplied to each AI.

The full-site bundle preserves the pinned static site and classifies external destinations as links. The browser’s live calculators and other interactive workflows remain on the publisher’s site. The five curated concepts cover the correspondence case only. [Em’s website](https://cyberdudeuk.github.io/ai-capability-governance/)

Each bundle also has a separate source-linked question, visual path and AI context
in its generated Pages root. The archive question tests what was captured and
what still needs the publisher's live site. The correspondence question traces
the proposed send capability, increased tier, draft-only limit, shadow mode and
human commitment. The authored questions are in [source/walkthroughs.json](source/walkthroughs.json).
These companions preserve the canonical Markdown and historical evaluation
downloads. They do not convert the illustrative case into local authorisation.
Each descriptor's snapshot digest binds its source nodes and qualified edges.
The publisher's pinned revision is recorded separately, so a local case annotation
cannot change unnoticed beneath an unchanged publisher revision.

## Standalone reader

[Open viz.html](https://chris-page-gov.github.io/okf-ai-capability-governance/viz.html) or save the HTML file from the Pages home page.
It embeds the searchable archive text, the worked-case relationship graph and both
illustrated guides. It follows the browsing pattern in the reference
[OKF example](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/bundles/acme_retail/viz.html).
Publisher citations and the canonical ZIP are links. The ZIP carries the original
snapshot bytes alongside the Markdown and semantic files.

## Reproduce and check

Use the locked uv environment with Python 3.12.11. Its dependencies match the
retained build requirements, including the Markdown renderer used for the
historical client evaluation. The local companion package version is separate
from the publisher's release 3.4.0.

```sh
uv sync --locked
uv run --locked python scripts/build.py
uv run --locked python scripts/build_site.py
uv run --locked python scripts/prepare_clients.py
uv run --locked python scripts/check_downloads.py
uv run --locked python scripts/build_explorer_companions.py
uv run --locked python scripts/build_explorer_companions.py --check
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/build_pages.py
uv run --locked python scripts/build_pages.py --check
uv run --locked python scripts/check_contracts.py
```

The check matches public download hashes to the evaluation record and rebuilt contents to the published files. The guarded Codex checks used the reviewed Explorer tooling at commit d0c5ad26843dd0e5ab1e7f9357838719ae9c3f83.

- [scripts/build.py](scripts/build.py) creates the small bundle and visualisation and checks the qualified assertions and graph parity.
- [scripts/build_site.py](scripts/build_site.py) creates the full archive and verifies captured bytes, structure and site membership.
- [scripts/prepare_clients.py](scripts/prepare_clients.py) makes the text fallback and provider skill packages after both builds.
- [Semantic contract](okf.semantic.json), [publication contract](okf.publication.json) and [local profile](profiles/README.md) record the source boundaries.

The installed guarded Codex skills validated both bundle roots and scanned the curated correspondence bundle. The frozen Explorer Bundle Wiki v1 profile targets OKF 0.2. This independent 0.3 profile reuses its assertion schema with a local validator, so the profile claim is scoped to this repository. [Pinned OKF 0.3 specification](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/SPEC.md) · [Explorer standards register](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-standards.md) · [Machine register](https://github.com/chris-page-gov/okf-explorer/blob/main/registry/okf-standards.json)

GitHub Pages publishes the draft pilot from protected main after build validation. The deployment job checks the served manifest and files against that build. The repository also provides the exact ZIPs and reading copies from the evaluation. [Repository status](REPOSITORY_STATUS.md) · [Licensing and attribution](LICENSE_DECISIONS.md)

The stable `validate` gate requires both deterministic core checks and independent
browser acceptance. Browser acceptance uses the exact Reader revision in
[source/explorer-consumer.json](source/explorer-consumer.json), exercises each
bundle through the native importer, then clicks each guide on desktop and mobile,
checks source selection and reload, and verifies every served candidate asset.
The companion targets the verified [Explorer 0.9.1 release](https://github.com/chris-page-gov/okf-explorer/releases/tag/v0.9.1).
The deployment promotes that candidate without rebuilding it. A local pass and
the historical client evaluation remain separate from current public acceptance.
The lifecycle check rejects changed paths until their source or generated
boundary is declared, and requires documentation and changelog updates alongside
controlled changes.

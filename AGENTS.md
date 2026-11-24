# Repository Instructions

- Write human-readable material in British English. Use the `en-GB` locale and
  `Europe/London` time zone; preserve exact code, schema fields, URLs and
  official titles where changing them would be incorrect.
- Treat Markdown and files under `source/` as authored source of truth.
- Do not edit `generated/` or release evidence by hand.
- Preserve unrelated work and use feature branches and pull requests.
- Keep the required validate check in lockstep with the distribution and its test evidence.
- Read `okf.semantic.json` and `okf.publication.json` before admitting source
  material or enabling any build, CI or publication command.
- Keep documentation and `CHANGELOG.md` in lockstep with controlled changes.
- Never create remotes, push, publish, or spend money implicitly.

- The source archive represents the pinned static Pages deployment. The
  correspondence bundle is the curated semantic case. Record the distinction
  when assessing coverage or changing either projection.
- Each evaluation claim needs a replayable prompt, artefact and observed result.
  Keep provider account details and tenant links out of durable reports.

- Rebuild and check the tracked downloads after changing the source or build steps.

- Use `uv sync --locked` and `uv run --locked python` with the repository's
  CPython 3.12.11 environment. Do not substitute host Python or an ad hoc environment.
- The lifecycle contract uses the pinned central publication schema; its HTTPS
  profile documentation link does not replace the local semantic profile's URN.
- Keep the evaluated downloads and client responses byte-identical. New Reader
  projections and worked questions have their own acceptance evidence.
- Reviewed local commands are `scripts/build.py`, `scripts/build_site.py`,
  `scripts/prepare_clients.py`, `scripts/check_downloads.py`,
  `scripts/build_explorer_companions.py`, `scripts/build_pages.py`,
  `scripts/check_contracts.py` and `scripts/verify_pages.py`, run through locked uv.
  Build scripts support their declared `--check` mode. Browser acceptance uses
  `node scripts/check_explorer_browser.mjs` with an exact pinned Explorer checkout.
- Treat command declarations as data. The contract checker validates their
  form and source script but never executes a declared command string.

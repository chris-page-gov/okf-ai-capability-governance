# Release the pilot

The public pilot contains two distinct OKF 0.3 bundle scopes. Keep the source
archive, illustrative correspondence case and historical client evaluation
separate in release claims. The local product version is independent of the
publisher's release 3.4.0.

The [validation workflow](../.github/workflows/validate.yml) produces the only
release candidate. The [publication contract](../okf.publication.json) declares
Pages and GitHub Releases as targets. Pages publishes automatically from protected
main; the owner-authorised release step freezes the accepted candidate manually.

1. Require successful core, browser, aggregate validation, deployment and live-file
   verification jobs for the exact main revision. Record its Git commit and the
   workflow run and artefact identifiers. The browser job checks the original
   manifest, Core version, source revision and file digests before installing the Reader.
2. Download the unchanged `capability-pages-COMMIT` Actions artifact. Check its
   complete file inventory against `publication.json`, including the source
   commit. Retain the original ZIP and its SHA-256 digest.
3. Run the actual public journey for each bundle on desktop and mobile: question,
   primary Reader record, declared lifecycle status, Evidence tab, original source card and
   reload. Verify every served asset against the downloaded candidate. Record
   failures as failures; correct the affected plane before release acceptance.
4. Create an annotated product-version tag at that exact accepted commit. Prepare
   a draft GitHub release with the unchanged Actions ZIP, a public acceptance
   report and a checksum manifest. Keep authenticated inventories and local paths
   out of the public report. Download every draft asset and compare its size and
   SHA-256 digest before publication.
5. Publish with platform immutable releases enabled. Download every published
   asset again, check anonymous public access, and verify GitHub's signed release
   attestation against the annotated tag and all asset digests. Git tag annotation
   and the signed release attestation are distinct evidence.

Promote the accepted artifact without rebuilding it. Preserve evaluated downloads,
upstream identity, source dates, custom semantic profile and qualified synthetic
assertions. Each bundle keeps its own question, graph, source and access evidence.
A technical release does not establish local authority approval or human, legal
or current-source acceptance. The whole estate programme has separate completion
gates.

Use the [central standards register](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-standards.md),
[machine register](https://github.com/chris-page-gov/okf-explorer/blob/main/registry/okf-standards.json)
and [public bundle catalogue](https://github.com/chris-page-gov/okf-explorer/blob/main/registry/okf-estate-registry.yaml)
for current and historical standards and explicitly public producer discovery.

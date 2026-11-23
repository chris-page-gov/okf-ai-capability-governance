# Repository status

- Lifecycle is a public research pilot hosted in the chris-page-gov companion repository.
- Upstream is release 3.4.0 at commit 9dd855ecfd8aece1b87c49eff2096b2d13d3fc98.
- The covered Pages inventory is derived from the publisher's deployment workflow. Twelve of its 13 files matched the live site. The .nojekyll deployment marker was retained from the pinned Git blob. Its public HTTP route returned 404.
- Publisher-owner discovery found 20 visible public repositories. The title filter identified this source repository. Its non-truncated recursive tree contains 90 files and no index.md. Other repositories remain outside the inspected scope.
- The curated semantic profile covers the correspondence case. The site archive preserves source structure and bytes.
- The checked downloads are available from the repository. GitHub Actions rebuilds both archives and checks their contents against the published files.
- Validation uses Ubuntu 24.04 with the Python 3.12.11 build used for the pilot.

Pages is built from the declared site inventory on protected main. The deployment
checks the live manifest against the exact source commit and validated file hashes.
The site provides its own OKF discovery descriptor, reading list, human pages and
raw OKF roots. Explorer’s central public catalogue is maintained separately.

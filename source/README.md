# Pilot source inputs

The domain is Em’s public correspondence-triage composite. The reader task is to
explain the effect of adding a send action, cite the published case, describe the
test conditions and flag the missing local approval. The primary consumers here
are a Markdown-capable assistant and an offline browser. Explorer import is a
separate compatibility question.

`pilot.json` contains edited concept text and explicit semantic relationships.
`snapshots/em-index.html.gz` preserves the public index from the pinned upstream
commit before any extraction. The build checks its uncompressed SHA-256, parses
only declared section locators, and records the digest of each normalised witness.
The public content is attributed to Em (cyberdudeuk) and contributors under the
publisher’s CC BY 4.0 declaration. Third-party material keeps its own terms.
The site snapshot remains in the repository source tree and is excluded from the
portable bundle.

The site-snapshot manifest enumerates the entire pinned Git tree and lists the
files included by the Pages deployment. The archive contains the 13 deployment
files and the publisher's code licence. The repository files outside that set
have inventory entries. The snapshots retain original bytes compressed with
gzip, and the site build handles JavaScript and CSS as data.

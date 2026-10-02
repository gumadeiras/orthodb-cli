# orthodb

Agent-friendly CLI for OrthoDB v12.

Repo:

```text
https://github.com/gumadeiras/orthodb-cli
```

Goals:

- cache official OrthoDB flat files locally with checksums
- answer common lookups from cached data when available
- fall back to the live OrthoDB URL API when local data is missing or too large
- emit machine-readable JSON by default for API responses and cache metadata
- stay easy to package for Homebrew

## Install

Homebrew:

```bash
brew tap gumadeiras/tap
brew install orthodb
```

PyPI with `pipx`:

```bash
pipx install orthodb
```

PyPI with plain `pip`:

```bash
python3 -m pip install orthodb
```

From source:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Examples

```bash
orthodb version
orthodb search p450 --level 33208 --singlecopy 0.8 --take 2
orthodb group 4977at9604
orthodb orthologs 4977at9604 --species 9606_0,10090_0
orthodb fasta 4977at9604 --species 9606_0 --output group.fa
orthodb cache manifest
orthodb cache download species
orthodb cache plan orthologs
orthodb cache index species
orthodb cache sync minimal --index
orthodb resolve 4977at9604
orthodb local species "Homo sapiens"
orthodb local og "olfactory"
orthodb export ogs --query "olfactory receptor" --limit 10
```

`/blast`, `/fasta`, and `/tab` calls are rate-limited to one request per
second, matching OrthoDB's published API guidance.

## Cache

Downloaded flat files and their derived SQLite index are persistent data. The
default root is:

```text
~/Library/Application Support/orthodb                 # macOS
$XDG_DATA_HOME/orthodb or ~/.local/share/orthodb      # Linux
%LOCALAPPDATA%\orthodb                                # Windows
```

Override with:

```bash
orthodb --cache-dir /path/to/cache cache status
```

The flat-file manifest is read from:

```text
https://data.orthodb.org/current/download/odb_data_dump
```

Large data files are intentionally not auto-downloaded. Use
`orthodb cache manifest` first, then download a named dataset.

`--timeout` must be a finite positive number of seconds. It applies to live
API calls, manifest requests, and flat-file downloads. For example:

```bash
orthodb --timeout 120 cache download species
```

Downloads verify the file against the manifest's MD5 by default. A matching
cached file is reused; a corrupt file is downloaded again. The new file replaces
the old file only after it is closed and passes verification. The option
`--no-verify` on `cache download` skips checksum checks for both new and existing files. The `md5`
field in download output is the expected manifest checksum; it does not prove
integrity when verification is disabled.

`cache status` and `cache plan` check file presence without reading large files
to compute checksums. Their `downloaded` fields mean that a path exists.
`cache plan` sets `will_download` from presence and the large-file gate; sync
still verifies existing files and can replace corrupt files that the plan lists
as downloaded. Sync output's `downloaded` list includes reused files.

An interrupted download returns exit code 130. Temporary files are closed and
removed on failure. If removal also fails, the original error is preserved and
the remaining partial-file path is reported on stderr.

Aliases match complete dataset filenames, so `species` cannot select
`level2species`, and `aa_fasta` cannot select `og_aa_fasta`. Multiple cached
versions of the same dataset are rejected; keep one version per cache directory.
If an older version built a species index from the wrong file, rebuild it:

```bash
orthodb cache index species
```

Curated sync profiles:

- `minimal`: species, levels, level-to-species
- `annotations`: minimal metadata plus OG annotations
- `orthologs`: OG tables, skipping multi-GB files unless `--include-large`

Build a local SQLite index from downloaded files:

```bash
orthodb cache index all
orthodb cache db
```

Indexed local queries:

```bash
orthodb local species "Homo sapiens"
orthodb local og "Cytochrome P450"
orthodb local gene P12345
orthodb local orthologs 4977at9604
orthodb export species --query "Homo sapiens" --limit 2
```

`export` emits newline-delimited JSON from the local SQLite index, capped by
`--limit`.

Resolve IDs before choosing a query path:

```bash
orthodb resolve 4977at9604
orthodb resolve 9606_0:0017fc
orthodb resolve P12345
```

## Release

Published versions are listed on the
[releases page](https://github.com/gumadeiras/orthodb-cli/releases).

Tag pushes like `vX.Y.Z` run the release workflow: build artifacts, create a
GitHub release, publish to PyPI, and update `gumadeiras/homebrew-tap`.

Release prerequisites:

- PyPI trusted publishing configured for this repo.
- `HOMEBREW_TAP_TOKEN` repository secret can write to
  `gumadeiras/homebrew-tap`.

Release artifacts are attached to GitHub releases for Homebrew packaging:

```text
https://github.com/gumadeiras/orthodb-cli/releases
```

Use the local wrapper described in [the release guide](docs/release.md).
Homebrew installation and formula updates are described in
[the packaging guide](docs/homebrew.md).

## Source Notes

Primary references:

- OrthoDB v12 user guide and URL API: <https://www.ezlab.org/orthodb_v12_userguide.html#api>
- OrthoDB current flat files: <https://data.orthodb.org/current/download/odb_data_dump>
- OrthoDB-py: <https://gitlab.com/ezlab/orthodb_py>

The official Python package is useful reference material, but this CLI uses
direct HTTP calls and local flat files for a smaller runtime surface and simpler
Homebrew packaging.

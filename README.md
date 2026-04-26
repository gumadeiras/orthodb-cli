# orthodb-cli

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
orthodb cache index species
orthodb cache sync minimal --index
orthodb local species "Homo sapiens"
orthodb local og "olfactory"
orthodb export ogs --query "olfactory receptor" --limit 10
```

`/blast`, `/fasta`, and `/tab` calls are rate-limited to one request per
second, matching OrthoDB's published API guidance.

## Cache

Default cache root:

```text
$XDG_CACHE_HOME/orthodb-cli
```

or:

```text
~/.cache/orthodb-cli
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

## Source Notes

Primary references:

- OrthoDB v12 user guide and URL API: <https://www.ezlab.org/orthodb_v12_userguide.html#api>
- OrthoDB current flat files: <https://data.orthodb.org/current/download/odb_data_dump>
- OrthoDB-py: <https://gitlab.com/ezlab/orthodb_py>

The official Python package is useful reference material, but this CLI uses
direct HTTP calls and local flat files for a smaller runtime surface and simpler
Homebrew packaging.

# Design Notes

## Shape

`orthodb-cli` has two data paths:

- live URL API queries for focused lookups
- cached official flat files for large local processing

The live API is the first implementation target because it has stable command
boundaries and small responses. Cached flat files are added as explicit,
checksum-verified downloads, then local query commands can incrementally grow
around the files users actually download.

## Why not wrap OrthoDB-py directly?

OrthoDB-py is MIT licensed and useful for behavior reference. This CLI does not
depend on it initially because direct HTTP keeps startup fast, minimizes
dependency risk for Homebrew, and lets the command surface be designed around
agent-readable output instead of Python objects.

## API Constraints

OrthoDB documents `https://data.orthodb.org/v12/CMD?...` as the URL API shape.
Most commands return JSON envelopes with `data`, `status`, and sometimes
`message`. `/fasta`, `/tab`, and `/og_description` return text formats.

OrthoDB rate-limits `/blast`, `/fasta`, and `/tab` to one request per second.
The CLI applies a process-local limiter before those calls.

## Download Strategy

The current flat-file manifest is served as an HTML table at:

```text
https://data.orthodb.org/current/download/odb_data_dump
```

Files include small tables such as species and levels, medium OG tables, and
multi-GB gene/sequence dumps. Downloads are explicit, streamed to a temporary
`.part` file, and verified with MD5 when the manifest provides it.

The download README says non-FASTA files are tab-separated and do not include
headers. Local commands must own their schema labels per dataset.

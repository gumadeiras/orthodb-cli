# AGENTS.md

## Project

`orthodb-cli` is a stdlib-only Python CLI for OrthoDB v12 live API queries and
checksum-verified flat-file caching.

## Rules

- Keep runtime dependencies at zero unless there is a strong packaging or
  performance reason.
- Keep command output machine-readable. Prefer JSON for structured data.
- Add resolver/export surfaces when they reduce the number of guesses an agent
  must make.
- Respect OrthoDB's published 1 request/second limit for `/blast`, `/fasta`,
  and `/tab`.
- Do not auto-download multi-GB flat files. Show manifest/status first, then
  require an explicit `cache download`.
- Keep SQLite indexes derived from cached source files; raw downloads remain
  the source of truth.
- If flat-file schemas change, update local parsers and docs together.

## Gates

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
```

Useful live smoke checks:

```bash
PYTHONPATH=src python3 -m orthodb_cli.cli version
PYTHONPATH=src python3 -m orthodb_cli.cli search p450 --take 2 --level 33208 --singlecopy 0.8
PYTHONPATH=src python3 -m orthodb_cli.cli cache manifest --refresh
```

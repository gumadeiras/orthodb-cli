# AGENTS.md

## Git

- Commit with `scripts/committer "<subject>" -- <path>...`; it stages only listed paths. Use `--body` or `--body-file` for commit bodies.

## Release

- Use `./scripts/release check <version>` for local preflight.
- Use `./scripts/release run <version>` only after explicit release approval.
- Tag pushes run the release workflow, publish GitHub assets, publish PyPI, and update `gumadeiras/homebrew-tap`.

## Project

`orthodb` is a stdlib-only Python CLI for OrthoDB v12 live API queries and
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
python3 -m build
```

Useful live smoke checks:

```bash
PYTHONPATH=src python3 -m orthodb_cli.cli version
PYTHONPATH=src python3 -m orthodb_cli.cli search p450 --take 2 --level 33208 --singlecopy 0.8
PYTHONPATH=src python3 -m orthodb_cli.cli cache manifest --refresh
```

Before release, verify a clean venv install:

```bash
python3 -m venv /tmp/orthodb-install
/tmp/orthodb-install/bin/python -m pip install .
/tmp/orthodb-install/bin/orthodb --version
```

## Changelog

- Keep `CHANGELOG.md` updated for user-facing changes. If a commit adds a feature, fix, behavior change, CLI change, GUI change, output-format change, install/release change, or other user-visible change, add or update an entry under the top `Unreleased` section in the same commit.
- Never edit released changelog sections for current work. Corrections, renames, and behavior changes after a release must be recorded only under the top `Unreleased` section unless Gustavo explicitly asks for release-history repair.
- Use these sections when they apply: `Features`, `Fixes`, and `Changes`.
- Omit empty sections.
- Write user-facing entries instead of repository chore notes.
- Do not include pure tests, internal refactors, CI-only changes, or docs-only changes unless they affect user behavior, API, installation, or usage.

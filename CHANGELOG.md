# Changelog

## Unreleased

### Changes

- Moved downloaded OrthoDB flat files and their derived SQLite index to the
  operating system's persistent application-data directory by default.
- Renamed the published PyPI and Homebrew package to `orthodb`.
- Updated release automation to the current GitHub Actions checkout, Python setup, and release actions.
- Added a local release wrapper for version sync, package validation, tagging, and release workflow verification.

## 0.1.5 - 2026-10-02

### Fixes

- Fixed cache downloads and sync failing with a missing-import error.
- Close download handles and remove partial files when a download, checksum
  check, or file replacement fails, including interrupted downloads.
- Apply `--timeout` to cache manifest requests and downloads; reject timeouts
  that are not finite positive numbers.
- Preserve the original download error and report the partial-file path if
  cleanup also fails.
- Report expected file and HTTP connection errors on stderr without a traceback.
- Select the correct source file for dataset aliases and reject ambiguous
  cached versions. Rebuild any species index previously created from
  level-to-species data with `orthodb cache index species`.
- Close SQLite connections after indexing, queries, exports, and ID resolution.

## 0.1.1 - 2026-05-05

### Changes

- Prepared the PyPI release flow.

## 0.1.0 - 2026-04-25

Initial release.

### Features

- Added Python package metadata and an agent-friendly OrthoDB CLI.
- Added live OrthoDB API queries and checksum-verified flat-file caching.
- Added SQLite cache indexing and FTS-backed local exports.
- Added resolver and cache planning commands.
- Added CI and release build workflows.

### Fixes

- Fixed package license metadata.

### Changes

- Documented OrthoDB CLI workflows, Homebrew formula preparation, release flow, and install paths.

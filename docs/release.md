# Release Guide

Use `scripts/release` from the repository root. The package version comes from
`src/orthodb_cli/__init__.py`. Commit the intended changes and changelog before
starting a release; the wrapper requires a clean working tree.

Local preflight for the version currently in the source:

```bash
./scripts/release check 0.1.4
```

`check` validates the version, runs `actionlint` when available, runs the tests,
builds the wheel and source archive, checks distribution metadata, and verifies
a clean wheel installation. It replaces the local `dist/` directory and does
not publish or push anything. Use the source version instead of `0.1.4` after
a version change. Run `python3 -m compileall -q src tests` as the additional
repository compile gate.

After explicit release approval:

```bash
./scripts/release run <next-version>
```

`run` updates the version, runs preflight, commits the version change, creates
and pushes the tag and branch, and waits for the release workflow. If the source
changes after preflight, repeat preflight before publishing.

Tag pushes such as `vX.Y.Z` trigger `.github/workflows/release.yml`. The workflow
builds and checks distributions, attaches them to a GitHub release, publishes
to PyPI, and updates `gumadeiras/homebrew-tap` from the source archive's SHA256.
Do not upload artifacts or edit the tap manually as part of the normal flow.

The workflow requires PyPI trusted publishing and the `HOMEBREW_TAP_TOKEN`
repository secret. `./scripts/release publish <version>` waits for an existing
tag's workflow; it does not create or push the tag.

See [Homebrew packaging](homebrew.md) for installation and formula details.

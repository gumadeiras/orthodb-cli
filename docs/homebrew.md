# Homebrew Packaging

Install from the tap:

```bash
brew tap gumadeiras/tap
brew install orthodb
```

The maintained formula is
[Formula/orthodb.rb](https://github.com/gumadeiras/homebrew-tap/blob/main/Formula/orthodb.rb).
It installs the package from a GitHub release source archive into a Python
virtual environment.

The release workflow updates the formula URL and SHA256 after the GitHub and
PyPI release jobs succeed. Use [the release wrapper](release.md) for normal
releases. The source archive checksum is checked by Homebrew; downloaded OrthoDB
datasets use the separate MD5 checksums from the OrthoDB manifest.

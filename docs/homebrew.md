# Homebrew Packaging

Do not publish the formula until a tagged release exists.

Draft formula shape for `gumadeiras/homebrew-tap`:

```ruby
class OrthodbCli < Formula
  include Language::Python::Virtualenv

  desc "Agent-friendly CLI for cached OrthoDB downloads and live API queries"
  homepage "https://github.com/gumadeiras/orthodb-cli"
  url "https://github.com/gumadeiras/orthodb-cli/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_TAG_ARCHIVE_SHA256"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "orthodb-cli", shell_output("#{bin}/orthodb --version")
  end
end
```

Release prep:

1. Tag `orthodb-cli`.
2. Let the Release workflow build artifacts.
3. Compute the GitHub tag archive checksum.
4. Add or update `Formula/orthodb-cli.rb` in `~/git/homebrew-tap`.


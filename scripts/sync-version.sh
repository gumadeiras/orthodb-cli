#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./scripts/sync-version.sh <version>
  ./scripts/sync-version.sh --check <version>
EOF
}

CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=1
  shift
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

VERSION="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="$ROOT_DIR/src/orthodb_cli/__init__.py"

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "error: version must look like 1.2.3" >&2
  exit 1
fi

current_version() { perl -ne 'print $1 if /^__version__ = "([^"]+)"/' "$VERSION_FILE"; }

if (( CHECK_ONLY )); then
  actual="$(current_version)"
  if [[ "$actual" != "$VERSION" ]]; then
    echo "error: package version is '$actual', expected '$VERSION'" >&2
    exit 1
  fi
  echo "Release version fields already match $VERSION."
  exit 0
fi

VERSION="$VERSION" perl -0pi -e \
  's/^__version__ = "[^"]+"/__version__ = "$ENV{VERSION}"/m or die "failed to update version\n";' \
  "$VERSION_FILE"

echo "Updated release version to $VERSION."

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import OrthoDBError

MANIFEST_URL = "https://data.orthodb.org/current/download/odb_data_dump"
DATASET_ALIASES = {
    "species": "species.tab.gz",
    "levels": "levels.tab.gz",
    "level2species": "level2species.tab.gz",
    "genes": "genes.tab.gz",
    "gene_xrefs": "gene_xrefs.tab.gz",
    "ogs": "OGs.tab.gz",
    "og2genes": "OG2genes.tab.gz",
    "og_pairs": "OG_pairs.tab.gz",
    "og_xrefs": "OG_xrefs.tab.gz",
    "aa_fasta": "aa_fasta.gz",
    "og_aa_fasta": "og_aa_fasta.gz",
    "cds_fasta": "cds_fasta.gz",
    "readme": "README.txt",
}


@dataclass(frozen=True)
class ManifestEntry:
    name: str
    url: str
    size: str
    description: str
    md5: str


def default_cache_dir() -> Path:
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "orthodb-cli"
    return Path.home() / ".cache" / "orthodb-cli"


def manifest_path(cache_dir: Path) -> Path:
    return cache_dir / "manifest.json"


def fetch_manifest(url: str = MANIFEST_URL, timeout: float = 60.0) -> list[ManifestEntry]:
    req = Request(url, headers={"User-Agent": "orthodb-cli/0.1"})
    try:
        with urlopen(req, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise OrthoDBError(f"manifest HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise OrthoDBError(f"manifest request failed: {exc.reason}") from exc
    return parse_manifest(html)


def parse_manifest(html: str) -> list[ManifestEntry]:
    parser = _ManifestParser()
    parser.feed(html)
    entries: list[ManifestEntry] = []
    for row in parser.rows:
        if len(row) != 4:
            continue
        file_cell, size, description, md5 = row
        name = file_cell["text"].strip()
        href = file_cell["href"].strip()
        if not name or name.lower() == "file":
            continue
        entries.append(ManifestEntry(name, href, size["text"].strip(), description["text"].strip(), md5["text"].strip()))
    return entries


def save_manifest(entries: Iterable[ManifestEntry], cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path(cache_dir)
    payload = [asdict(entry) for entry in entries]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_manifest(cache_dir: Path) -> list[ManifestEntry]:
    path = manifest_path(cache_dir)
    if not path.exists():
        entries = fetch_manifest()
        save_manifest(entries, cache_dir)
        return entries
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ManifestEntry(**item) for item in payload]


def resolve_dataset(entries: Iterable[ManifestEntry], dataset: str) -> ManifestEntry:
    needle = DATASET_ALIASES.get(dataset, dataset)
    if needle == dataset:
        matches = [entry for entry in entries if entry.name == needle]
    else:
        matches = [entry for entry in entries if entry.name == needle or entry.name.endswith(f"_{needle}")]
    if not matches:
        names = ", ".join(sorted(DATASET_ALIASES))
        raise OrthoDBError(f"unknown dataset {dataset!r}; known aliases: {names}")
    if len(matches) > 1:
        raise OrthoDBError(f"dataset {dataset!r} matched multiple files")
    return matches[0]


def cache_status(cache_dir: Path, entries: Iterable[ManifestEntry]) -> list[dict[str, object]]:
    rows = []
    for entry in entries:
        path = cache_dir / entry.name
        rows.append(
            {
                "name": entry.name,
                "size": entry.size,
                "description": entry.description,
                "md5": entry.md5,
                "path": str(path),
                "downloaded": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return rows


def download_entry(entry: ManifestEntry, cache_dir: Path, verify: bool = True) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / entry.name
    if destination.exists() and (not verify or md5sum(destination) == entry.md5):
        return destination

    fd, tmp_name = tempfile.mkstemp(prefix=f".{entry.name}.", suffix=".part", dir=cache_dir)
    os.close(fd)
    tmp_path = Path(tmp_name)
    req = Request(entry.url, headers={"User-Agent": "orthodb-cli/0.1"})
    try:
        with urlopen(req, timeout=60) as response, tmp_path.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    if verify:
        got = md5sum(tmp_path)
        if got != entry.md5:
            tmp_path.unlink(missing_ok=True)
            raise OrthoDBError(f"MD5 mismatch for {entry.name}: expected {entry.md5}, got {got}")
    tmp_path.replace(destination)
    return destination


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_cached_file(cache_dir: Path, alias: str) -> Path | None:
    suffix = DATASET_ALIASES.get(alias, alias)
    pattern = re.compile(re.escape(suffix) + r"$")
    for path in cache_dir.glob("*"):
        if path.is_file() and pattern.search(path.name):
            return path
    return None


class _ManifestParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[dict[str, str]]] = []
        self._current_row: list[dict[str, str]] | None = None
        self._current_cell: dict[str, str] | None = None
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._in_cell = True
            self._current_cell = {"text": "", "href": ""}
        elif tag == "a" and self._current_cell is not None:
            self._current_cell["href"] = attrs_dict.get("href", "")

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._current_cell is not None:
            self._current_cell["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.append(self._current_cell)
            self._current_cell = None
            self._in_cell = False
        elif tag == "tr" and self._current_row is not None:
            self.rows.append(self._current_row)
            self._current_row = None

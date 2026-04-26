from __future__ import annotations

import csv
import gzip
from pathlib import Path
from typing import Iterable

from .cache import find_cached_file
from .errors import OrthoDBError


def species_search(cache_dir: Path, query: str, limit: int = 20) -> list[dict[str, str]]:
    path = find_cached_file(cache_dir, "species")
    if path is None:
        raise OrthoDBError("species cache missing; run `orthodb cache download species`")

    needle = query.casefold()
    matches: list[dict[str, str]] = []
    for row in iter_tsv(path):
        haystack = " ".join(row).casefold()
        if needle in haystack:
            matches.append(row_to_record(row))
            if len(matches) >= limit:
                break
    return matches


def iter_tsv(path: Path) -> Iterable[list[str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        yield from reader


def row_to_record(row: list[str]) -> dict[str, str]:
    keys = [
        "ncbi_tax_id",
        "organism_id",
        "scientific_name",
        "assembly_id",
        "clustered_gene_count",
        "og_count",
        "mapping_type",
    ]
    record: dict[str, str] = {}
    for index, value in enumerate(row):
        key = keys[index] if index < len(keys) else f"field_{index + 1}"
        record[key] = value
    return record

from __future__ import annotations

import csv
import gzip
import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from .cache import find_cached_file
from .errors import OrthoDBError


def species_search(cache_dir: Path, query: str, limit: int = 20) -> list[dict[str, str]]:
    db_results = query_sqlite(cache_dir, "species", query, limit)
    if db_results is not None:
        return db_results

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


def og_search(cache_dir: Path, query: str, limit: int = 20) -> list[dict[str, str]]:
    results = query_sqlite(cache_dir, "ogs", query, limit)
    if results is None:
        raise OrthoDBError("OG index missing; run `orthodb cache download ogs` and `orthodb cache index ogs`")
    return results


def gene_search(cache_dir: Path, query: str, limit: int = 20) -> list[dict[str, str]]:
    results = query_sqlite(cache_dir, "genes", query, limit)
    if results is None:
        raise OrthoDBError("gene index missing; run `orthodb cache download genes` and `orthodb cache index genes`")
    return results


def ortholog_gene_ids(cache_dir: Path, og_id: str, limit: int = 10_000) -> list[dict[str, str]]:
    db_file = cache_dir / "orthodb.sqlite"
    if not db_file.exists():
        raise OrthoDBError("SQLite index missing; run `orthodb cache index og2genes`")

    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "og2genes"):
            raise OrthoDBError("og2genes index missing; run `orthodb cache download og2genes` and `orthodb cache index og2genes`")
        has_genes = table_exists(conn, "genes")
        has_species = table_exists(conn, "species")
        if has_genes and has_species:
            rows = conn.execute(
                """
                SELECT
                  og2genes.og_id,
                  og2genes.gene_id,
                  genes.organism_id,
                  species.scientific_name,
                  genes.uniprot_id,
                  genes.ncbi_gene,
                  genes.description
                FROM og2genes
                LEFT JOIN genes ON genes.gene_id = og2genes.gene_id
                LEFT JOIN species ON species.organism_id = genes.organism_id
                WHERE og2genes.og_id = ?
                LIMIT ?
                """,
                (og_id, limit),
            )
        elif has_genes:
            rows = conn.execute(
                """
                SELECT og2genes.og_id, og2genes.gene_id, genes.organism_id, genes.uniprot_id, genes.ncbi_gene, genes.description
                FROM og2genes
                LEFT JOIN genes ON genes.gene_id = og2genes.gene_id
                WHERE og2genes.og_id = ?
                LIMIT ?
                """,
                (og_id, limit),
            )
        else:
            rows = conn.execute("SELECT og_id, gene_id FROM og2genes WHERE og_id = ? LIMIT ?", (og_id, limit))
        return [dict(row) for row in rows]


def export_ndjson(cache_dir: Path, table: str, query: str | None = None, limit: int = 1_000) -> str:
    db_file = cache_dir / "orthodb.sqlite"
    if not db_file.exists():
        raise OrthoDBError("SQLite index missing; run `orthodb cache index`")
    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, table):
            raise OrthoDBError(f"SQLite table {table!r} missing; run `orthodb cache index`")
        rows = select_rows(conn, table, query, limit)
        return "".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows)


def query_sqlite(cache_dir: Path, table: str, query: str, limit: int) -> list[dict[str, str]] | None:
    db_file = cache_dir / "orthodb.sqlite"
    if not db_file.exists():
        return None
    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, table):
            return None
        fts_results = query_fts(conn, table, query, limit)
        if fts_results is not None:
            return fts_results
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
        predicates = " OR ".join(f"{column} LIKE ?" for column in columns)
        params = [f"%{query}%"] * len(columns)
        rows = conn.execute(f"SELECT * FROM {table} WHERE {predicates} LIMIT ?", (*params, limit))
        return [dict(row) for row in rows]


def select_rows(conn: sqlite3.Connection, table: str, query: str | None, limit: int) -> Iterable[sqlite3.Row]:
    if query:
        fts_rows = select_fts_rows(conn, table, query, limit)
        if fts_rows is not None:
            return fts_rows
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
        predicates = " OR ".join(f"{column} LIKE ?" for column in columns)
        params = [f"%{query}%"] * len(columns)
        return conn.execute(f"SELECT * FROM {table} WHERE {predicates} LIMIT ?", (*params, limit)).fetchall()
    return conn.execute(f"SELECT * FROM {table} LIMIT ?", (limit,)).fetchall()


def query_fts(conn: sqlite3.Connection, table: str, query: str, limit: int) -> list[dict[str, str]] | None:
    fts_table = f"fts_{table}"
    if not table_exists(conn, fts_table):
        return None
    match = fts_match(query)
    if not match:
        return None
    try:
        rows = conn.execute(
            f"""
            SELECT {table}.*
            FROM {fts_table}
            JOIN {table} ON {table}.rowid = {fts_table}.rowid
            WHERE {fts_table} MATCH ?
            ORDER BY bm25({fts_table})
            LIMIT ?
            """,
            (match, limit),
        )
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return None


def select_fts_rows(conn: sqlite3.Connection, table: str, query: str, limit: int) -> list[sqlite3.Row] | None:
    fts_table = f"fts_{table}"
    if not table_exists(conn, fts_table):
        return None
    match = fts_match(query)
    if not match:
        return None
    try:
        return conn.execute(
            f"""
            SELECT {table}.*
            FROM {fts_table}
            JOIN {table} ON {table}.rowid = {fts_table}.rowid
            WHERE {fts_table} MATCH ?
            ORDER BY bm25({fts_table})
            LIMIT ?
            """,
            (match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return None


def fts_match(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_:-]+", query)
    return " ".join(f'"{term}"*' for term in terms)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


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

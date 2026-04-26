from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

OG_RE = re.compile(r"^\d+at\d+$")
ORGANISM_RE = re.compile(r"^\d+_\d+$")
GENE_RE = re.compile(r"^\d+_\d+:[A-Za-z0-9_.-]+$")
NCBI_TAX_RE = re.compile(r"^\d+$")
UNIPROT_RE = re.compile(r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9])$")


def identify(value: str, cache_dir: Path | None = None) -> dict[str, Any]:
    value = value.strip()
    kind = infer_kind(value)
    result: dict[str, Any] = {
        "query": value,
        "kind": kind,
        "local": {},
        "suggested_commands": suggested_commands(value, kind),
    }
    if cache_dir is not None:
        result["local"] = local_hints(value, kind, cache_dir)
    return result


def infer_kind(value: str) -> str:
    if OG_RE.match(value):
        return "orthologous_group"
    if GENE_RE.match(value):
        return "gene"
    if ORGANISM_RE.match(value):
        return "organism"
    if UNIPROT_RE.match(value):
        return "uniprot"
    if NCBI_TAX_RE.match(value):
        return "ncbi_tax_id"
    return "text"


def suggested_commands(value: str, kind: str) -> list[str]:
    if kind == "orthologous_group":
        return [
            f"orthodb group {value}",
            f"orthodb orthologs {value}",
            f"orthodb local orthologs {value}",
        ]
    if kind == "gene":
        return [
            f"orthodb details {value}",
            f"orthodb local gene {value}",
        ]
    if kind == "organism":
        return [
            f"orthodb local species {value}",
            f"orthodb genesearch --ncbi {value.split('_', 1)[0]}",
        ]
    if kind == "uniprot":
        return [
            f"orthodb genesearch {value}",
            f"orthodb local gene {value}",
        ]
    if kind == "ncbi_tax_id":
        return [
            f"orthodb species --clade {value}",
            f"orthodb local species {value}",
        ]
    return [
        f"orthodb search {value}",
        f"orthodb genesearch {value}",
        f"orthodb local og {value}",
        f"orthodb local gene {value}",
    ]


def local_hints(value: str, kind: str, cache_dir: Path) -> dict[str, Any]:
    db_file = cache_dir / "orthodb.sqlite"
    if not db_file.exists():
        return {"indexed": False}
    with sqlite3.connect(db_file) as conn:
        conn.row_factory = sqlite3.Row
        if kind == "orthologous_group":
            return {"indexed": True, "ogs": lookup_one(conn, "ogs", "og_id", value), "og2genes_count": count_matches(conn, "og2genes", "og_id", value)}
        if kind == "gene":
            return {"indexed": True, "genes": lookup_one(conn, "genes", "gene_id", value), "og2genes": lookup_many(conn, "og2genes", "gene_id", value, 5)}
        if kind == "organism":
            return {"indexed": True, "species": lookup_one(conn, "species", "organism_id", value)}
        if kind == "ncbi_tax_id":
            return {"indexed": True, "species": lookup_many(conn, "species", "ncbi_tax_id", value, 5), "levels": lookup_one(conn, "levels", "level_tax_id", value)}
        if kind == "uniprot":
            return {"indexed": True, "genes": lookup_many(conn, "genes", "uniprot_id", value, 5)}
        return {"indexed": True}


def lookup_one(conn: sqlite3.Connection, table: str, column: str, value: str) -> dict[str, str] | None:
    if not table_exists(conn, table):
        return None
    row = conn.execute(f"SELECT * FROM {table} WHERE {column} = ? LIMIT 1", (value,)).fetchone()
    return dict(row) if row is not None else None


def lookup_many(conn: sqlite3.Connection, table: str, column: str, value: str, limit: int) -> list[dict[str, str]]:
    if not table_exists(conn, table):
        return []
    rows = conn.execute(f"SELECT * FROM {table} WHERE {column} = ? LIMIT ?", (value, limit)).fetchall()
    return [dict(row) for row in rows]


def count_matches(conn: sqlite3.Connection, table: str, column: str, value: str) -> int | None:
    if not table_exists(conn, table):
        return None
    return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (value,)).fetchone()[0])


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None

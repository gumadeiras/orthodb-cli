from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .cache import find_cached_file
from .errors import OrthoDBError
from .local import iter_tsv

DB_NAME = "orthodb.sqlite"
INSERT_CHUNK_SIZE = 10_000


@dataclass(frozen=True)
class DatasetSchema:
    alias: str
    table: str
    columns: tuple[str, ...]
    indexes: tuple[tuple[str, ...], ...]


SCHEMAS: dict[str, DatasetSchema] = {
    "species": DatasetSchema(
        alias="species",
        table="species",
        columns=(
            "ncbi_tax_id",
            "organism_id",
            "scientific_name",
            "assembly_id",
            "clustered_gene_count",
            "og_count",
            "mapping_type",
        ),
        indexes=(("organism_id",), ("ncbi_tax_id",), ("scientific_name",)),
    ),
    "levels": DatasetSchema(
        alias="levels",
        table="levels",
        columns=("level_tax_id", "scientific_name", "gene_count", "og_count", "species_count"),
        indexes=(("level_tax_id",), ("scientific_name",)),
    ),
    "ogs": DatasetSchema(
        alias="ogs",
        table="ogs",
        columns=("og_id", "level_tax_id", "name"),
        indexes=(("og_id",), ("level_tax_id",), ("name",)),
    ),
    "og2genes": DatasetSchema(
        alias="og2genes",
        table="og2genes",
        columns=("og_id", "gene_id"),
        indexes=(("og_id",), ("gene_id",)),
    ),
    "genes": DatasetSchema(
        alias="genes",
        table="genes",
        columns=(
            "gene_id",
            "organism_id",
            "original_sequence_id",
            "synonyms",
            "uniprot_id",
            "ensembl_ids",
            "ncbi_gene",
            "description",
            "genomic_coordinates",
            "genomic_dna_id",
            "chromosome",
        ),
        indexes=(("gene_id",), ("organism_id",), ("uniprot_id",), ("ncbi_gene",)),
    ),
}


def db_path(cache_dir: Path) -> Path:
    return cache_dir / DB_NAME


def connect(cache_dir: Path) -> sqlite3.Connection:
    cache_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(cache_dir))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def index_cache(cache_dir: Path, aliases: Sequence[str] | None = None) -> list[dict[str, object]]:
    selected = list(aliases) if aliases else sorted(SCHEMAS)
    unknown = [alias for alias in selected if alias not in SCHEMAS]
    if unknown:
        raise OrthoDBError(f"unsupported index dataset(s): {', '.join(unknown)}")

    results = []
    with connect(cache_dir) as conn:
        for alias in selected:
            path = find_cached_file(cache_dir, alias)
            if path is None:
                continue
            schema = SCHEMAS[alias]
            rows = index_file(conn, schema, path)
            results.append({"dataset": alias, "table": schema.table, "rows": rows, "path": str(path)})
    return results


def index_file(conn: sqlite3.Connection, schema: DatasetSchema, path: Path) -> int:
    cols_sql = ", ".join(f"{column} TEXT" for column in schema.columns)
    conn.execute(f"DROP TABLE IF EXISTS {schema.table}")
    conn.execute(f"CREATE TABLE {schema.table} ({cols_sql})")

    placeholders = ", ".join("?" for _ in schema.columns)
    insert_sql = f"INSERT INTO {schema.table} VALUES ({placeholders})"
    count = 0
    batch: list[tuple[str, ...]] = []
    for row in iter_tsv(path):
        batch.append(normalize_row(row, len(schema.columns)))
        if len(batch) >= INSERT_CHUNK_SIZE:
            conn.executemany(insert_sql, batch)
            count += len(batch)
            batch.clear()
    if batch:
        conn.executemany(insert_sql, batch)
        count += len(batch)

    for columns in schema.indexes:
        index_name = f"idx_{schema.table}_{'_'.join(columns)}"
        conn.execute(f"CREATE INDEX {index_name} ON {schema.table} ({', '.join(columns)})")
    conn.commit()
    return count


def normalize_row(row: Sequence[str], width: int) -> tuple[str, ...]:
    values = list(row[:width])
    values.extend("" for _ in range(width - len(values)))
    return tuple(values)


def db_status(cache_dir: Path) -> dict[str, object]:
    path = db_path(cache_dir)
    if not path.exists():
        return {"path": str(path), "exists": False, "tables": []}
    tables = []
    with connect(cache_dir) as conn:
        for schema in SCHEMAS.values():
            if table_exists(conn, schema.table):
                count = conn.execute(f"SELECT COUNT(*) FROM {schema.table}").fetchone()[0]
                tables.append({"dataset": schema.alias, "table": schema.table, "rows": count})
    return {"path": str(path), "exists": True, "tables": tables}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


def require_table(conn: sqlite3.Connection, table: str) -> None:
    if not table_exists(conn, table):
        raise OrthoDBError(f"SQLite table {table!r} missing; run `orthodb cache index`")


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, str]]:
    return [dict(row) for row in rows]


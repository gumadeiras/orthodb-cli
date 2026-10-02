import gzip
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orthodb_cli.db import db_status, index_cache
from orthodb_cli.errors import OrthoDBError
from orthodb_cli.identify import identify
from orthodb_cli.local import export_ndjson, fts_match, og_search, ortholog_gene_ids, species_search


class DbTests(unittest.TestCase):
    def test_index_species_and_og_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            write_gzip(
                cache_dir / "odb12v2_species.tab.gz",
                "9606\t9606_0\tHomo sapiens\tGCA_018503575.1\t1\t2\tC\n",
            )
            write_gzip(cache_dir / "odb12v2_OGs.tab.gz", "4977at9604\t9604\tolfactory receptor\n")
            write_gzip(cache_dir / "odb12v2_OG2genes.tab.gz", "4977at9604\t9606_0:0017fc\n")

            result = index_cache(cache_dir, ["species", "ogs", "og2genes"])

            self.assertEqual([item["dataset"] for item in result], ["species", "ogs", "og2genes"])
            self.assertEqual(species_search(cache_dir, "Homo sapiens")[0]["organism_id"], "9606_0")
            self.assertEqual(og_search(cache_dir, "olfactory")[0]["og_id"], "4977at9604")
            self.assertEqual(ortholog_gene_ids(cache_dir, "4977at9604")[0]["gene_id"], "9606_0:0017fc")
            self.assertIn('"og_id": "4977at9604"', export_ndjson(cache_dir, "ogs", "olfactory", limit=1))
            status = db_status(cache_dir)
            self.assertTrue(status["exists"])
            self.assertTrue(status["tables"][0]["fts"])

    def test_fts_match_quotes_terms(self):
        self.assertEqual(fts_match("Homo sapiens"), '"Homo"* "sapiens"*')

    def test_connections_close_after_success_and_failure(self):
        connections = []
        original_connect = sqlite3.connect

        def record_connection(*args, **kwargs):
            conn = original_connect(*args, **kwargs)
            connections.append(conn)
            return conn

        with tempfile.TemporaryDirectory() as tmp, patch("sqlite3.connect", side_effect=record_connection):
            cache_dir = Path(tmp)
            write_gzip(cache_dir / "odb12v2_species.tab.gz", "9606\t9606_0\tHomo sapiens\tassembly\t1\t2\tC\n")
            write_gzip(cache_dir / "odb12v2_OG2genes.tab.gz", "4977at9604\t9606_0:0017fc\n")
            index_cache(cache_dir, ["species", "og2genes"])
            db_status(cache_dir)
            species_search(cache_dir, "Homo sapiens")
            export_ndjson(cache_dir, "species")
            ortholog_gene_ids(cache_dir, "4977at9604")
            identify("Homo sapiens", cache_dir)
            with self.assertRaises(OrthoDBError):
                export_ndjson(cache_dir, "genes")
            with patch("orthodb_cli.db.index_file", side_effect=OSError("index failed")), self.assertRaises(OSError):
                index_cache(cache_dir, ["species"])
            corrupt_dir = cache_dir / "corrupt"
            corrupt_dir.mkdir()
            (corrupt_dir / "orthodb.sqlite").write_bytes(b"not a SQLite database")
            with self.assertRaises(sqlite3.DatabaseError):
                index_cache(corrupt_dir)
            self.assertGreaterEqual(len(connections), 9)
            for conn in connections:
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute("SELECT 1")


def write_gzip(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    unittest.main()

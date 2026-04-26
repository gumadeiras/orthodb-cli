import gzip
import tempfile
import unittest
from pathlib import Path

from orthodb_cli.db import db_status, index_cache
from orthodb_cli.local import og_search, ortholog_gene_ids, species_search


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
            self.assertTrue(db_status(cache_dir)["exists"])


def write_gzip(path: Path, text: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)


if __name__ == "__main__":
    unittest.main()


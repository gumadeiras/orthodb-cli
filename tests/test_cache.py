import unittest

from orthodb_cli.cache import parse_manifest, resolve_dataset
from orthodb_cli.cli import is_large


HTML = """
<table>
<tr><th>File</th><th>Size</th><th>Description</th><th>MD5sum</th></tr>
<tr>
  <td><a href=https://data.orthodb.org/current/download/odb_data_dump/odb12v2_species.tab.gz>odb12v2_species.tab.gz</a></td>
  <td>0.6 MB</td>
  <td>Ortho DB organism ids</td>
  <td>05f75664f4e1ed9af3ac7aa19ca68d8f</td>
</tr>
<tr>
  <td><a href=https://data.orthodb.org/current/download/odb_data_dump/odb12v2_level2species.tab.gz>odb12v2_level2species.tab.gz</a></td>
  <td>240.8 kB</td>
  <td>correspondence between level ids and organism ids</td>
  <td>c6b7f73ac554d1cae3df2d2a6eb9fdce</td>
</tr>
</table>
"""


class CacheTests(unittest.TestCase):
    def test_parse_manifest(self):
        entries = parse_manifest(HTML)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].name, "odb12v2_species.tab.gz")
        self.assertEqual(entries[0].size, "0.6 MB")
        self.assertEqual(entries[0].md5, "05f75664f4e1ed9af3ac7aa19ca68d8f")

    def test_resolve_dataset_alias(self):
        entry = resolve_dataset(parse_manifest(HTML), "species")

        self.assertEqual(entry.name, "odb12v2_species.tab.gz")

    def test_large_size_detection(self):
        self.assertTrue(is_large("4.5 GB"))
        self.assertFalse(is_large("128.2 MB"))


if __name__ == "__main__":
    unittest.main()

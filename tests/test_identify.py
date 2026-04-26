import unittest

from orthodb_cli.identify import identify, infer_kind


class IdentifyTests(unittest.TestCase):
    def test_infers_common_orthodb_ids(self):
        self.assertEqual(infer_kind("4977at9604"), "orthologous_group")
        self.assertEqual(infer_kind("9606_0:0017fc"), "gene")
        self.assertEqual(infer_kind("9606_0"), "organism")
        self.assertEqual(infer_kind("9606"), "ncbi_tax_id")
        self.assertEqual(infer_kind("P12345"), "uniprot")

    def test_resolve_suggests_commands(self):
        result = identify("4977at9604")

        self.assertEqual(result["kind"], "orthologous_group")
        self.assertIn("orthodb group 4977at9604", result["suggested_commands"])


if __name__ == "__main__":
    unittest.main()

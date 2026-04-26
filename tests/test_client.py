import unittest

from orthodb_cli.client import OrthoDBClient, clean_params


class ClientTests(unittest.TestCase):
    def test_build_url_strips_empty_values(self):
        client = OrthoDBClient()

        url = client.build_url("search", {"query": "p450", "take": 2, "skip": None})

        self.assertEqual(url, "https://data.orthodb.org/v12/search?query=p450&take=2")

    def test_clean_params_joins_lists(self):
        self.assertEqual(clean_params({"species": ["9606_0", "10090_0"]}), {"species": "9606_0,10090_0"})


if __name__ == "__main__":
    unittest.main()


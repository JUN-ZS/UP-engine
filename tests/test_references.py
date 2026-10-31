import tempfile
import unittest
from pathlib import Path

from ige.references import ReferenceCatalog


class ReferenceCatalogTests(unittest.TestCase):
    def test_catalog_finds_a8b_and_skill_references(self):
        catalog = ReferenceCatalog.load()
        result = catalog.resolve("a8b78fe5-2654-4f6f-84e3-c1dfbee61004", role="identity_master", skill="PATH1E")
        self.assertEqual(result["availability"], "external_asset_reference_only")
        self.assertEqual(result["materialization"], "reference_only")

    def test_skill_search_returns_skin_refs(self):
        catalog = ReferenceCatalog.load()
        ids = {item["asset_id"] for item in catalog.search(skill="SKIN_MAT")}
        self.assertTrue({"9e1cd1e9-f229-4b21-bf4c-91b2d045e08b", "2befbe5e-751c-434a-a39f-ad4bf8ed4374", "d4d2d76d-c467-46e9-96f2-eb6ba58ec5f6"}.issubset(ids))

    def test_unknown_reference_is_not_guessed(self):
        catalog = ReferenceCatalog.load()
        with self.assertRaises(KeyError):
            catalog.inspect("not-a-known-ref")

    def test_skill_filter_is_case_insensitive(self):
        catalog = ReferenceCatalog.load()
        self.assertTrue(catalog.search(skill="detail6"))


if __name__ == "__main__":
    unittest.main()

"""Regression tests for the independent English France catalog."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker

from build_catalog import BASE_URL, build_catalog, validate_catalog
from build_readme import CATEGORIES, load_servers, render_badges, render_catalog
from test_quality import BASE_SERVER
from validate_servers import describe

ROOT = Path(__file__).resolve().parent.parent


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schema/server.schema.json").read_text())
        cls.validator = Draft202012Validator(cls.schema, format_checker=FormatChecker())

    def test_empty_catalog_is_valid_and_has_zero_counts(self):
        catalog = build_catalog([])
        validate_catalog(catalog)
        self.assertEqual(catalog["count"], 0)
        self.assertEqual(catalog["servers"], [])
        self.assertTrue(all(category["count"] == 0 for category in catalog["categories"]))
        self.assertEqual(render_catalog([]), "")
        self.assertIn('alt="0 servers"', render_badges([]))
        self.assertIn('alt="0 categories"', render_badges([]))

    def test_source_loader_still_rejects_missing_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("build_readme.SERVERS_DIR", Path(directory)):
                with self.assertRaisesRegex(SystemExit, "no servers found"):
                    load_servers()

    def test_unassessed_metadata_survives_without_creating_a_score(self):
        server = copy.deepcopy(BASE_SERVER)
        server["last_verified"] = "2026-09-06"
        self.assertTrue(self.validator.is_valid(server))
        catalog = build_catalog([server])
        validate_catalog(catalog)
        self.assertEqual(catalog["count"], 1)
        self.assertEqual(sum(c["count"] for c in catalog["categories"]), 1)
        entry = catalog["servers"][0]
        self.assertEqual(entry["last_verified"], "2026-09-06")
        self.assertIsNone(entry["readiness_score"])
        self.assertNotIn("quality", entry)
        self.assertNotIn("readiness_score", server)

    def test_verification_date_is_optional_but_must_be_a_real_iso_date(self):
        self.assertTrue(self.validator.is_valid(BASE_SERVER))
        for value in ["2026-02-30", "06/09/2026", "2026-09-06T12:00:00Z", None]:
            with self.subTest(value=value):
                server = dict(BASE_SERVER, last_verified=value)
                self.assertFalse(self.validator.is_valid(server))

    def test_categories_match_schema_and_issue_form(self):
        slugs = [category.slug for category in CATEGORIES]
        self.assertEqual(slugs, self.schema["$defs"]["server"]["properties"]["category"]["enum"])
        issue_form = (ROOT / ".github/ISSUE_TEMPLATE/new-server.yml").read_text()
        for slug in slugs:
            self.assertIn(f"        - {slug}\n", issue_form)

    def test_public_identifiers_point_to_france(self):
        self.assertEqual(BASE_URL, "https://bsab.github.io/france-mcp-servers")
        catalog = build_catalog([])
        self.assertEqual(catalog["source"], "https://github.com/bsab/france-mcp-servers")
        self.assertEqual(catalog["$schema"], f"{BASE_URL}/schema/catalog.schema.json")
        self.assertEqual(self.schema["$id"], f"{BASE_URL}/schema/server.schema.json")
        schema = json.loads((ROOT / "schema/catalog.schema.json").read_text())
        self.assertEqual(schema["$id"], catalog["$schema"])

    def test_page_uses_english_locale_and_unassessed_labels(self):
        template = (ROOT / "scripts/templates/index.html").read_text()
        self.assertIn('<html lang="en">', template)
        self.assertIn("France MCP Servers 🇫🇷", template)
        self.assertIn("toLocaleString('en-GB')", template)
        self.assertIn("localeCompare(b.name, 'en')", template)
        self.assertIn('<option value="unassessed">Unassessed</option>', template)
        self.assertIn("Unassessed does not mean zero.", template)
        self.assertIn("Unable to load the catalog:", template)

    def test_missing_url_validation_message_is_in_english(self):
        server = copy.deepcopy(BASE_SERVER)
        del server["repository_url"]
        errors = list(self.validator.iter_errors(server))
        self.assertTrue(errors)
        self.assertIn(
            "at least one of repository_url, site_url or mcp_endpoint is required",
            [describe(error) for error in errors],
        )


if __name__ == "__main__":
    unittest.main()

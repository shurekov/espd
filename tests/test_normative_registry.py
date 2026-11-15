import unittest

from backend.normative_registry import (
    build_profile_normative,
    get_normative_document_path,
)


class NormativeRegistryTests(unittest.TestCase):
    def test_builds_references_from_existing_rules(self):
        result = build_profile_normative("ved")

        self.assertEqual(
            result["document"],
            {
                "id": "gost-19.507-79",
                "standard": "ГОСТ 19.507-79",
                "pdf_url": ("/api/normative-documents/gost-19.507-79.pdf"),
            },
        )

        self.assertEqual(len(result["rules"]), 6)
        self.assertEqual(
            result["rules"]["VED-01"]["source"],
            "пункт 3",
        )
        self.assertEqual(
            result["rules"]["VED-03"]["source"],
            "обязательное приложение 1",
        )
        self.assertIn(
            "Документы на программу",
            result["rules"]["VED-01"]["requirement"],
        )
        self.assertEqual(result["rules"]["VED-01"]["page"], 1)
        self.assertEqual(result["rules"]["VED-03"]["page"], 3)
        self.assertEqual(result["rules"]["VED-05"]["page"], 2)
        self.assertEqual(result["rules"]["VED-06"]["page"], 2)

    def test_resolves_document_path_without_accepting_paths(self):
        path = get_normative_document_path("gost-19.507-79")

        self.assertEqual(path.name, "gost-19.507-79.pdf")
        self.assertEqual(path.parent.name, "normative")

        with self.assertRaises(KeyError):
            get_normative_document_path("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()

import unittest

from strata.search import compile_query, run_search


class SearchTests(unittest.TestCase):
    def test_boolean_phrase_and_not(self):
        matcher = compile_query('"wrongful termination" AND NOT severance')
        self.assertTrue(matcher("this discusses wrongful termination in an email"))
        self.assertFalse(matcher("wrongful termination and severance package"))

    def test_proximity(self):
        matcher = compile_query('"fired" W/5 "email"')
        self.assertTrue(matcher("she was fired after the email chain surfaced"))
        self.assertFalse(matcher("she was fired. unrelated content. later there was an email"))

    def test_search_output(self):
        index = {
            "memo.pdf": {
                "title": "memo.pdf",
                "chunks": [{"id": "p1-1", "label": "p1-1", "page": 1, "text": "termination email", "snippet": "termination email"}],
            }
        }
        results = run_search(index, ["termination AND email"])
        self.assertEqual(results["termination AND email"]["total_hits"], 1)
        self.assertEqual(results["termination AND email"]["document_count"], 1)


if __name__ == "__main__":
    unittest.main()

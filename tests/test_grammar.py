"""Validate the TextMate grammar and keep its word lists in sync with the
language definition.

Run with:  python -m unittest tests.test_grammar
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sandy.tokens import KEYWORDS
from sandy.builtins import BUILTIN_NAMES

GRAMMAR_PATH = os.path.join(ROOT, "editors", "vscode", "syntaxes",
                            "sandy.tmLanguage.json")


def _alternation_words(pattern):
    """Extract words from the first `(a|b|c)` alternation in a regex."""
    m = re.search(r"\(([a-z_0-9|]+)\)", pattern)
    return set(m.group(1).split("|")) if m else set()


class TestGrammar(unittest.TestCase):
    def setUp(self):
        with open(GRAMMAR_PATH, encoding="utf-8") as f:
            self.grammar = json.load(f)
        self.repo = self.grammar["repository"]

    def test_scope_and_filetype(self):
        self.assertEqual(self.grammar["scopeName"], "source.sandy")
        self.assertIn("sy", self.grammar["fileTypes"])

    def test_regexes_compile(self):
        # A sanity check that the patterns are well-formed regexes.
        def walk(node):
            if isinstance(node, dict):
                for key in ("match", "begin", "end"):
                    if key in node:
                        re.compile(node[key])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(self.grammar)

    def test_keywords_in_sync(self):
        words = set()
        for pat in self.repo["keywords"]["patterns"]:
            words |= _alternation_words(pat["match"])
            m = re.fullmatch(r"\\b(\w+)\\b", pat["match"])
            if m:
                words.add(m.group(1))
        words |= _alternation_words(self.repo["constants"]["match"])
        expected = set(KEYWORDS) | {"as"}
        self.assertEqual(words, expected,
                         "grammar keywords out of sync with tokens.KEYWORDS")

    def test_builtins_in_sync(self):
        words = _alternation_words(self.repo["builtins"]["match"])
        self.assertEqual(words, set(BUILTIN_NAMES),
                         "grammar builtins out of sync with BUILTIN_NAMES")


class TestExtensionManifest(unittest.TestCase):
    def test_package_points_at_existing_files(self):
        base = os.path.join(ROOT, "editors", "vscode")
        with open(os.path.join(base, "package.json"), encoding="utf-8") as f:
            pkg = json.load(f)
        grammar = pkg["contributes"]["grammars"][0]
        self.assertEqual(grammar["scopeName"], "source.sandy")
        self.assertTrue(os.path.exists(os.path.join(base, grammar["path"])))
        lang = pkg["contributes"]["languages"][0]
        self.assertIn(".sy", lang["extensions"])
        self.assertTrue(os.path.exists(os.path.join(base, lang["configuration"])))


if __name__ == "__main__":
    unittest.main()

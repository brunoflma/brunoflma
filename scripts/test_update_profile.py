"""Check public-data boundaries and safe SVG rendering."""
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser

from update_profile import ASSETS, ROOT, render, summarize


class CardLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.cards = []
        self.sources = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'a':
            self.href = values.get('href')
        if tag == 'img' and '/projects/' in values.get('src', ''):
            self.cards.append((values['src'], self.href))
        if tag == 'source' and '/projects/' in values.get('srcset', ''):
            self.sources.append(values['srcset'])

    def handle_endtag(self, tag):
        if tag == 'a':
            self.href = None


def repository(name, **overrides):
    return {"name": name, "visibility": "public", "private": False, "fork": False,
            "owner": {"login": "brunoflma"}, "stargazers_count": 2,
            "pushed_at": "2026-09-20T12:00:00Z", "archived": False, **overrides}


class ProfileTests(unittest.TestCase):
    def test_four_cards_have_their_own_landing_page_link(self):
        parser = CardLinks()
        parser.feed((ROOT / 'README.md').read_text(encoding='utf-8'))
        expected = [('jurisprudenciaia', 'jurisprudenciaia-mcp'), ('jusmanizer', 'jusmanizer'),
                    ('session-linker', 'claude-session-linker'), ('md-studio', 'md-studio')]
        self.assertEqual(parser.cards, [(f'./assets/projects/{asset}.svg', f'https://brunoflma.github.io/{project}/') for asset, project in expected])
        self.assertEqual(parser.sources, [f'./assets/projects/{asset}-mobile.svg' for asset, _ in expected])
        for source, _ in parser.cards:
            tree = ET.fromstring((ROOT / source).read_text(encoding='utf-8'))
            self.assertEqual(tree.attrib['width'], '1200')
        for source in parser.sources:
            tree = ET.fromstring((ROOT / source).read_text(encoding='utf-8'))
            self.assertEqual(tree.attrib['width'], '600')

    def test_only_owned_public_projects_count(self):
        rows = [repository("public"), repository("secret", private=True, visibility="private"),
                repository("fork", fork=True), repository("brunoflma"),
                repository("other", owner={"login": "someone"}),
                repository("unknown", visibility=None)]
        result = summarize(rows, date(2026, 9, 20))
        self.assertEqual((result["projects"], result["stars"]), (1, 2))
        self.assertEqual(result["recent"], [{"name": "public", "date": "2026-09-20"}])

    def test_latest_three_exclude_archived_and_unpushed(self):
        rows = [repository("old", pushed_at="2026-01-01T00:00:00Z"),
                repository("archived", archived=True), repository("empty", pushed_at=None),
                repository("c"), repository("b"), repository("a")]
        result = summarize(rows, date(2026, 9, 20))
        self.assertEqual([x["name"] for x in result["recent"]], ["c", "b", "a"])
        self.assertEqual(result["projects"], 6)

    def test_both_panels_escape_names_and_handle_empty_data(self):
        for path in ASSETS:
            source = path.read_text(encoding="utf-8")
            for rows in [[], [repository('<script>&"')]]:
                result = render(source, summarize(rows, date(2026, 9, 20)))
                ET.fromstring(result)
                self.assertNotIn("<script>", result)
                if rows:
                    self.assertIn("&lt;script&gt;&amp;&quot;", result)

    def test_missing_svg_field_fails_before_update(self):
        with self.assertRaises(ValueError):
            render("<svg/>", summarize([], date(2026, 9, 20)))


if __name__ == "__main__":
    unittest.main()

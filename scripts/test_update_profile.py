"""Check public-data boundaries and safe SVG rendering."""
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from update_profile import ASSETS, ROOT, SVG, main, render, summarize


PROJECTS = [('jurisprudenciaia', 'https://brunoflma.github.io/jurisprudenciaia-mcp/'),
            ('jusmanizer', 'https://brunoflma.github.io/jusmanizer/'),
            ('session-linker', 'https://brunoflma.github.io/claude-session-linker/'),
            ('md-studio', 'https://brunoflma.github.io/md-studio/'),
            ('eluxi', 'https://eluxi.bfldevlabs.studio/'),
            ('fons', 'https://fons.bfldevlabs.studio/'),
            ('zetema', 'https://zetema.bfldevlabs.studio/'),
            ('dissero', 'https://dissero.bfldevlabs.studio/')]


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
        if tag == 'img' and Path(values.get('src', '')).stem in dict(PROJECTS):
            self.cards.append((values['src'], self.href))
        if tag == 'source' and Path(values.get('srcset', '')).stem.removesuffix('-mobile') in dict(PROJECTS):
            self.sources.append(values['srcset'])

    def handle_endtag(self, tag):
        if tag == 'a':
            self.href = None


def repository(name, **overrides):
    return {"name": name, "visibility": "public", "private": False, "fork": False,
            "owner": {"login": "brunoflma"}, "stargazers_count": 2,
            "pushed_at": "2026-09-20T12:00:00Z", "archived": False, **overrides}


class ProfileTests(unittest.TestCase):
    def test_public_and_ecosystem_cards_have_equal_size_and_their_own_links(self):
        parser = CardLinks()
        parser.feed((ROOT / 'README.md').read_text(encoding='utf-8'))
        self.assertEqual(parser.cards, [(f'./assets/lex-profile/{asset}.svg', url) for asset, url in PROJECTS])
        self.assertEqual(parser.sources, [f'./assets/lex-profile/{asset}-mobile.svg' for asset, _ in PROJECTS])
        for source, _ in parser.cards:
            tree = ET.fromstring((ROOT / source).read_text(encoding='utf-8'))
            self.assertEqual(tree.attrib['width'], '1200')
            self.assertEqual(tree.attrib['height'], '280')
        for source in parser.sources:
            tree = ET.fromstring((ROOT / source).read_text(encoding='utf-8'))
            self.assertEqual(tree.attrib['width'], '600')
            self.assertEqual(tree.attrib['height'], '440')

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
                    field = ET.fromstring(result).find(f'.//{{{SVG}}}g[@id="recent-name-0"]')
                    self.assertEqual(field.get("aria-label"), '<script>&"')
                self.assertEqual(render(result, summarize(rows, date(2026, 9, 20))), result)

    def test_dates_follow_fortaleza_instead_of_utc(self):
        result = summarize([repository("late", pushed_at="2026-10-24T01:00:00Z")], date(2026, 10, 24))
        self.assertEqual(result["recent"][0]["date"], "2026-10-23")

    def test_provider_failure_preserves_both_panels(self):
        before = [path.read_bytes() for path in ASSETS]
        with patch('sys.argv', ['update_profile.py', '--write']), \
                patch('update_profile.fetch_repositories', side_effect=OSError('provider unavailable')):
            with self.assertRaises(OSError):
                main()
        self.assertEqual([path.read_bytes() for path in ASSETS], before)

    def test_dynamic_fields_update_without_changing_the_static_artwork(self):
        data = {"projects": 12, "stars": 1234, "recent": [{"name": "a" * 45, "date": "2026-10-23"}], "as_of": "2026-10-24"}
        for path in ASSETS:
            source = path.read_text(encoding="utf-8")
            original, changed = ET.fromstring(source), ET.fromstring(render(source, data))
            fields = {node.get("id"): node for node in changed.findall(f'{{{SVG}}}g') if node.get("id")}
            self.assertEqual(fields["metric-projects"].get("aria-label"), "12")
            self.assertEqual(fields["metric-stars"].get("aria-label"), "1,2k")
            self.assertEqual(fields["recent-name-1"].get("aria-label"), "—")
            limit = 26 if original.get("width") == "600" else 38
            self.assertEqual(fields["recent-name-0"].get("aria-label"), "a" * (limit - 1) + "…")
            self.assertEqual(fields["updated-at"].get("aria-label"), "Atualizado em 24/10/2026")
            static = lambda tree: [ET.tostring(node) for node in tree if not node.get("id")]
            self.assertEqual(static(original), static(changed))

    def test_missing_svg_field_fails_before_update(self):
        with self.assertRaises(ValueError):
            render("<svg/>", summarize([], date(2026, 9, 20)))


if __name__ == "__main__":
    unittest.main()

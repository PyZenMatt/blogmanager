from django.test import TestCase
from blog.utils import slug_from_filename, extract_frontmatter


class SlugParsingTests(TestCase):
    def test_slug_from_frontmatter_precedence(self):
        fm_text = """---\nslug: custom-slug\n---\nContent"""
        fm = extract_frontmatter(fm_text)
        self.assertEqual(fm.get('slug'), 'custom-slug')

    def test_filename_fallback(self):
        self.assertEqual(slug_from_filename('2025-11-05-kundalini.md'), 'kundalini')
        self.assertEqual(slug_from_filename('2024-01-09-e-mc2-xyz.md'), 'e-mc2-xyz')
        self.assertEqual(slug_from_filename('2023-12-31-a.md'), 'a')
        # suspicious short-date-only filename should not produce '05-11-...'
        self.assertEqual(slug_from_filename('05-11-kundalini.md'), '05-11-kundalini')

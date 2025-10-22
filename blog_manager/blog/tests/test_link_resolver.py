from django.test import TestCase
from blog.link_resolver import LinkResolver, SHORTCODE_RE


class ParserTests(TestCase):
    def test_shortcode_parse_simple(self):
        body = "This is a link [[post:my-slug|Click here]] in text"
        parsed = list(LinkResolver.parse_shortcodes(body))
        self.assertEqual(len(parsed), 1)
        raw, typ, target, anchor, text = parsed[0]
        self.assertEqual(typ, 'post')
        self.assertEqual(target, 'my-slug')
        self.assertEqual(text, 'Click here')

    def test_ext_preserved(self):
        body = "[[ext:https://example.com/page|visit]]"
        parsed = list(LinkResolver.parse_shortcodes(body))
        self.assertEqual(parsed[0][1], 'ext')

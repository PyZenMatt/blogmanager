from django.test import TestCase
from blog.link_resolver import LinkResolver
from django.apps import apps
from django.conf import settings


class ResolverDBTests(TestCase):
    def setUp(self):
        Site = apps.get_model('blog', 'Site')
        Author = apps.get_model('blog', 'Author')
        Post = apps.get_model('blog', 'Post')

        self.site = Site.objects.create(name='Site A', domain='https://a.example', slug='site-a')
        self.site_b = Site.objects.create(name='Site B', domain='https://b.example', slug='site-b')
        author = Author.objects.create(name='Auth', slug='auth')

        # Post in site A
        self.post_a = Post.objects.create(site=self.site, title='Post A', slug='post-a', author=author, content='')
        # Post in site B
        self.post_b = Post.objects.create(site=self.site_b, title='Post B', slug='post-b', author=author, content='')

    def test_resolve_post_same_site_uses_relative(self):
        body = 'See [[post:post-a|here]]'
        resolved, errors = LinkResolver.resolve(body, self.site)
        self.assertFalse(errors)
        self.assertIn("relative_url", resolved)

    def test_resolve_post_cross_site_absolute(self):
        body = 'Link [[post:post-b|other]]'
        resolved, errors = LinkResolver.resolve(body, self.site)
        self.assertFalse(errors)
        self.assertIn('https://b.example', resolved)

    def test_unresolved_slug_errors(self):
        body = 'Unknown [[post:does-not-exist|X]]'
        resolved, errors = LinkResolver.resolve(body, self.site)
        self.assertTrue(errors)

    def test_anchor_slugification(self):
        body = 'See [[post:post-a#My Section|sec]]'
        resolved, errors = LinkResolver.resolve(body, self.site)
        self.assertFalse(errors)
        self.assertIn('#my-section', resolved)


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

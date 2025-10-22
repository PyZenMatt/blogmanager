from blog_manager.blog.link_resolver import LinkResolver, _slugify_header


def test_parse_simple_shortcode():
    body = "This is a link [[post:my-slug|Click here]] in text"
    parsed = list(LinkResolver.parse_shortcodes(body))
    assert len(parsed) == 1
    raw, typ, target, anchor, text = parsed[0]
    assert typ == 'post'
    assert target == 'my-slug'
    assert text == 'Click here'


def test_slugify_header_examples():
    assert _slugify_header('My Section') == 'my-section'
    assert _slugify_header('Café & résumé!') == 'caf-rsum'
    assert _slugify_header('Section: 1. Overview') == 'section-1-overview'

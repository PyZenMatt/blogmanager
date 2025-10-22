from blog_manager.blog.link_resolver import LinkResolver, LinkResolutionError
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def exists(self):
        return bool(self._items)

    def count(self):
        return len(self._items)

    def first(self):
        return self._items[0] if self._items else None

    def filter(self, **kwargs):
        items = self._items
        if 'site' in kwargs:
            site = kwargs['site']
            items = [i for i in items if getattr(i, 'site', None) == site]
        return FakeQuery(items)


class FakePostModel:
    def __init__(self, posts):
        self._posts = posts

    class objects:
        _posts = []

        @classmethod
        def filter(cls, **kwargs):
            slug = kwargs.get('slug')
            items = [p for p in cls._posts if p.slug == slug]
            return FakeQuery(items)


def make_post(slug, site_id, domain, title='T'):
    site = SimpleNamespace(id=site_id, domain=domain)
    post = SimpleNamespace(slug=slug, site=site, site_id=site_id, title=title)
    # minimal front-matter required by build_post_relpath
    post.content = "---\ncategories: [test]\n---\nBody"
    return post


def test_resolve_same_site(monkeypatch):
    # current site id 1
    current_site = SimpleNamespace(id=1, domain='https://a.example')
    p = make_post('post-a', 1, 'https://a.example', title='Post A')
    FakePostModel.objects._posts = [p]

    def fake_get_model(app_label, model_name):
        return FakePostModel

    monkeypatch.setattr('django.apps.apps.get_model', fake_get_model)

    body = 'See [[post:post-a|here]]'
    resolved, errors = LinkResolver.resolve(body, current_site)
    assert not errors
    assert 'relative_url' in resolved


def test_resolve_cross_site_absolute(monkeypatch):
    current_site = SimpleNamespace(id=1, domain='https://a.example')
    p = make_post('post-b', 2, 'b.example', title='Post B')
    FakePostModel.objects._posts = [p]

    def fake_get_model(app_label, model_name):
        return FakePostModel

    monkeypatch.setattr('django.apps.apps.get_model', fake_get_model)

    body = 'Link [[post:post-b|other]]'
    resolved, errors = LinkResolver.resolve(body, current_site)
    assert not errors
    assert 'https://b.example' in resolved


def test_unresolved_slug(monkeypatch):
    current_site = SimpleNamespace(id=1, domain='https://a.example')
    FakePostModel.objects._posts = []

    def fake_get_model(app_label, model_name):
        return FakePostModel

    monkeypatch.setattr('django.apps.apps.get_model', fake_get_model)

    body = 'Unknown [[post:does-not-exist|X]]'
    resolved, errors = LinkResolver.resolve(body, current_site)
    assert errors


def test_ambiguous_slug_error(monkeypatch):
    current_site = SimpleNamespace(id=1, domain='https://a.example')
    p1 = make_post('dup', 2, 'b.example')
    p2 = make_post('dup', 3, 'c.example')
    FakePostModel.objects._posts = [p1, p2]

    def fake_get_model(app_label, model_name):
        return FakePostModel

    monkeypatch.setattr('django.apps.apps.get_model', fake_get_model)

    body = 'Amb [[post:dup|D]]'
    resolved, errors = LinkResolver.resolve(body, current_site)
    assert errors

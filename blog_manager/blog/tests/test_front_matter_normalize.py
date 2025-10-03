import pytest
from types import SimpleNamespace
from blog.exporter import _front_matter
import yaml


class DummyPost(SimpleNamespace):
    pass


def _get_fm_from_render(post):
    md = _front_matter(post, site={})
    # extract yaml between ---
    if not md:
        return {}
    assert md.startswith('---\n')
    content = md[len('---\n'):]  # drop leading
    idx = content.find('\n---\n')
    yaml_text = content[:idx]
    return yaml.safe_load(yaml_text)


def test_cluster_only():
    post = DummyPost()
    # simulate post.categories returning list-like with slug attribute
    class C:
        def __init__(self, slug):
            self.slug = slug
            self.cluster_slug = slug
            self.subcluster_slug = None
    post.categories = SimpleNamespace(all=lambda: [C('django')])
    post.content = ''
    fm = _get_fm_from_render(post)
    assert 'categories' in fm
    assert isinstance(fm['categories'], list)
    assert fm['categories'][0] == 'django'
    assert 'subcluster' not in fm


def test_cluster_and_subcluster():
    post = DummyPost()
    class C:
        def __init__(self, slug, sub):
            self.slug = slug
            self.cluster_slug = slug
            self.subcluster_slug = sub
    post.categories = SimpleNamespace(all=lambda: [C('django', 'forms')])
    post.content = ''
    fm = _get_fm_from_render(post)
    assert fm['categories'] == ['django']
    assert fm.get('subcluster') == 'forms'


def test_legacy_cluster_slash_in_categories():
    post = DummyPost()
    # no M2M categories, but legacy front-matter present
    post.categories = SimpleNamespace(all=lambda: [])
    post.content = '---\ncategories: [django/forms]\n---\nBody'
    fm = _get_fm_from_render(post)
    assert fm['categories'] == ['django']
    assert fm.get('subcluster') == 'forms'

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings

from blog.exporter import export_post


class DummyPost(SimpleNamespace):
    def render_relative_path(self):
        return "_posts/2025-08-15-demo.md"

    def render_markdown(self):
        return "body"

    def save(self, **kwargs):
        pass


@pytest.mark.django_db
def test_exporter_uses_blog_repo_base(tmp_path, monkeypatch):
    site_dir = tmp_path / "mysite"
    site_dir.mkdir()
    monkeypatch.setattr(settings, "BLOG_REPO_BASE", str(tmp_path))
    site = SimpleNamespace(slug="mysite", repo_path="")
    post = DummyPost(site=site, slug="demo", export_hash="")

    def run_fake(cmd, cwd=None, capture_output=True, text=True, check=True, env=None):
        m = MagicMock()
        m.returncode = 0
        m.stdout = ""
        if cmd[1:3] == ["remote", "get-url"]:
            m.stdout = "https://github.com/acme/repo.git\n"
        if cmd[1:2] == ["status"]:
            m.stdout = " M _posts/2025-08-15-demo.md\n"
        if cmd[1:2] == ["rev-list"]:
            m.stdout = "0\n"
        return m

    with patch("blog.exporter.subprocess.run", side_effect=run_fake):
        os.environ["GIT_TOKEN"] = "tkn"
        export_post(post)
        assert (site_dir / "_posts" / "2025-08-15-demo.md").exists()

import os
import pytest
from unittest.mock import patch, MagicMock
from blog.exporter import export_post

class DummyPost:
    def __init__(self, site, slug, body="x", export_hash=""):
        self.site = site
        self.slug = slug
        self._body = body
        self.export_hash = export_hash
        self.id = 1
    def render_relative_path(self): return f"_posts/2025-08-15-{self.slug}.md"
    def render_markdown(self): return self._body
    def save(self, update_fields=None): pass

class DummySite:
    def __init__(self, repo_path): self.repo_path = repo_path

@pytest.mark.django_db
def test_writes_when_file_missing(tmp_path, monkeypatch):
    site = DummySite(str(tmp_path))
    post = DummyPost(site, "abc", body="content")

    # Mock git helpers
    def run_fake(cmd, cwd=None, capture_output=True, text=True, check=True, env=None):
        args = cmd[1:]
        m = MagicMock()
        m.returncode = 0
        m.stdout = ""
        if args[:2] == ["remote","get-url"]:
            m.stdout = "https://github.com/acme/repo.git\n"
        if args[:1] == ["status"]:
            m.stdout = " M _posts/2025-08-15-abc.md\n"
        if args[:1] == ["rev-list"]:
            m.stdout = "0\n"
        return m
    with patch("blog.exporter.subprocess.run", side_effect=run_fake):
        os.environ["GIT_TOKEN"] = "tkn"
        export_post(post)
        assert (tmp_path / "_posts/2025-08-15-abc.md").exists()

@pytest.mark.django_db
def test_push_if_ahead(tmp_path, monkeypatch):
    # File presente, hash invariato → ahead => push
    site = DummySite(str(tmp_path))
    rel = "_posts/2025-08-15-abc.md"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("content", encoding="utf-8")
    post = DummyPost(site, "abc", body="content", export_hash="d41d8cd98f")  # finto

    calls = []
    def run_fake(cmd, cwd=None, capture_output=True, text=True, check=True, env=None):
        args = cmd[1:]
        calls.append(args)
        m = MagicMock(); m.returncode = 0; m.stdout = ""
        if args[:1]==["remote"]: m.stdout = "https://github.com/acme/repo.git\n"
        if args[:1]==["status"]: m.stdout = ""
        if args[:1]==["rev-list"]: m.stdout = "2\n"  # ahead
        return m
    with patch("blog.exporter.subprocess.run", side_effect=run_fake):
        os.environ["GIT_TOKEN"]="tkn"
        export_post(post)
        # Verifica che sia stata tentata la push
        assert any(a[0]=="push" for a in calls)

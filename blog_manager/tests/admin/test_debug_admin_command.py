import pytest
from django.core.management import call_command
from django.apps import apps
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

def test_debug_admin_change_command_smoke(capsys):
    User = get_user_model()
    su = User.objects.create_superuser("admin", "admin@example.com", "x")
    Post = apps.get_model("blog", "Post")
    p = Post.objects.create(title="T", slug="t", site_id=1)
    call_command("debug_admin_change", "blog.Post", str(p.pk), username="admin")
    out = capsys.readouterr().out
    assert "OK: status_code=" in out

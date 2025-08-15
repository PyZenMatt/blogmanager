import os
import pytest
from django.urls import path

pytestmark = pytest.mark.django_db

from django.test import override_settings


def boom_view(request):
    raise RuntimeError("BOOM")

urlpatterns = [path("boom/", boom_view, name="boom")]

@override_settings(ROOT_URLCONF=__name__)
def test_verbose_mw_logs_exc(caplog, settings, monkeypatch):
    # attiva middleware via env flag
    monkeypatch.setenv("ENABLE_VERBOSE_ERRORS", "true")
    from django.test import Client
    c = Client()
    with caplog.at_level("ERROR"):
        resp = c.get("/boom/")
        assert resp.status_code == 500
        # deve aver loggato il messaggio con TRACEBACK
        joined = "\n".join([r.message for r in caplog.records])
        assert "BOOM" in joined
        assert "TRACEBACK" in joined

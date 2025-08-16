import importlib
import os

import pytest


def test_package_is_importable():
    """
    Garantisce che il package 'blog_manager' sia importabile nel contesto test.
    Fornisce un errore chiaro se la struttura non è corretta.
    """
    mod = importlib.import_module("blog_manager")
    assert hasattr(mod, "__file__")


@pytest.mark.django_db
def test_django_setup_and_check(settings):
    """
    Verifica che Django si avvii con i settings di default (dev) e che 'check' passi.
    """
    from django.core.management import call_command

    # Se il runner non ha DJANGO_SETTINGS_MODULE, imponiamo quello di default.
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "blog_manager.settings.dev",
    )

    call_command("check")

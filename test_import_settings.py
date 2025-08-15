#!/usr/bin/env python3
# test_import_settings.py
# Prints environment info and attempts to import candidate settings modules.

import sys
import importlib
import traceback
import os

print("Python executable:", sys.executable)
print("Working dir:", os.getcwd())
print("\nsys.path (first 20 entries):")
for i, p in enumerate(sys.path[:20], 1):
    print(f"{i:2d}. {p}")

def try_import(name):
    print("\n---")
    print("Trying import:", name)
    try:
        mod = importlib.import_module(name)
        print("SUCCESS:", name)
        print("module file:", getattr(mod, "__file__", "<package or builtin>"))
        # show a couple helpful attributes if present
        for attr in ("BASE_DIR", "DEBUG", "INSTALLED_APPS"):
            if hasattr(mod, attr):
                print(f"{attr} =", getattr(mod, attr))
    except Exception:
        print("IMPORT FAILED:")
        traceback.print_exc()

# Try the two common possibilities
try_import("blog_manager.settings")
try_import("blog_manager.blog_manager.settings")

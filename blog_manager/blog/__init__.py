# shim package so imports like `import blog.models` resolve to `blog_manager.blog` modules
# This keeps tests and historical imports working without changing many files.

from importlib import import_module
import sys

# Load the real package and make this package act as an alias for it.
_real_pkg = import_module("blog_manager.blog")

# Allow import machinery to find submodules (e.g. `blog.models`) by
# exposing the real package __path__ on this shim package.
__path__ = getattr(_real_pkg, "__path__", [])

# Re-export commonly used attributes and set module-level helpers
__all__ = getattr(_real_pkg, "__all__", [])

def __getattr__(name):
    return getattr(_real_pkg, name)

def __dir__():
    return sorted(list(globals().keys()) + dir(_real_pkg))

# Also register the real package in sys.modules under the short name when
# possible to improve compatibility with importlib internals.
sys.modules.setdefault("blog", _real_pkg)

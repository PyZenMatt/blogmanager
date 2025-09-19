import hashlib
import os
from typing import Tuple, Dict, Any
import re
import yaml


def split_front_matter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML front matter using PyYAML. Returns (fm_dict, body).
    If no front matter present returns ({}, content).

    This function is permissive: it accepts optional leading whitespace/newlines
    before the initial '---' and extracts the first YAML block delimited by '---'.
    """
    if not content:
        return {}, content
    # Look for a YAML front-matter block near the start (allow leading blank lines)
    m = re.search(r"^\s*---\s*\n(.*?)\n---\s*\n", content, flags=re.S | re.M)
    if m:
        raw_fm = m.group(1)
        body_start = m.end()
        body = content[body_start:]
        try:
            fm = yaml.safe_load(raw_fm) or {}
        except Exception:
            fm = {}
        return fm, body
    return {}, content


def compute_exported_hash(fm: Dict[str, Any], body: str) -> str:
    """Compute canonical md5 hash of YAML front-matter (sorted keys) and body.
    Returns first 10 hex chars to match exporter behaviour.
    """
    # Serialize front matter deterministically: sort keys and use YAML dump
    try:
        fm_serial = yaml.safe_dump(fm, sort_keys=True)
    except Exception:
        fm_serial = ""
    body_text = body if body.endswith("\n") else body + "\n"
    data = (fm_serial + "\n" + body_text).encode("utf-8")
    return hashlib.md5(data).hexdigest()[:10]


def iter_post_files(repo_dir: str, posts_dir: str = "_posts"):
    """Yield (rel_path, abs_path) for markdown files under posts_dir inside repo_dir."""
    base = os.path.join(repo_dir, posts_dir)
    if not os.path.isdir(base):
        return
    for root, _, files in os.walk(base):
        for fn in files:
            if not fn.lower().endswith(".md"):
                continue
            abs_path = os.path.join(root, fn)
            rel_path = os.path.relpath(abs_path, repo_dir).replace(os.path.sep, "/")
            yield rel_path, abs_path

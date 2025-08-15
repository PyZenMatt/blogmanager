import re

from django.utils.text import slugify


def slugify_title(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip()).lower()
    return slugify(s)[:180]


def clip(s, n):
    return (s[: n - 1] + "…") if s and len(s) > n else s


def extract_plain(md: str) -> str:
    # Remove basic markdown syntax
    text = re.sub(r"[`*_>#\-!\[\]\(\)]", " ", md or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def meta_defaults(title, body_plain, cats: list[str], tags: list[str]):
    meta_title = clip(title, 70)
    meta_desc = clip(body_plain, 160)
    kws = ", ".join(sorted(set([*cats, *tags])))[:255]
    return meta_title, meta_desc, kws

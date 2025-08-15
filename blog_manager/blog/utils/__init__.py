import hashlib
from typing import Dict, Any

def build_jekyll_front_matter(post) -> Dict[str, Any]:
	# Minimale (espandere secondo il vostro schema)
	return {
		"title": getattr(post, "title", ""),
		"slug": getattr(post, "slug", ""),
		"date": getattr(post, "date", getattr(post, "published_at", None)),
		"categories": getattr(post, "categories", []) or [],
		"tags": getattr(post, "tags", []) or [],
		"status": getattr(post, "status", "draft"),
	}

def render_markdown_for_export(post) -> str:
	fm = build_jekyll_front_matter(post)
	# YAML deterministico: chiavi ordinate
	lines = ["---"]
	for k in sorted(fm.keys()):
		v = fm[k]
		if isinstance(v, (list, tuple)):
			lines.append(f"{k}:")
			for item in v:
				lines.append(f"  - {item}")
		else:
			lines.append(f"{k}: {v}")
	lines.append("---")
	body = getattr(post, "content", getattr(post, "content_markdown", "")).rstrip() + "\n"
	return "\n".join(lines) + "\n\n" + body

def content_hash(post) -> str:
	data = render_markdown_for_export(post).encode("utf-8")
	return hashlib.sha256(data).hexdigest()

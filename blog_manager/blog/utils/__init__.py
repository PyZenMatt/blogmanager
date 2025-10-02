import hashlib
from typing import Dict, Any
import re
import yaml
from typing import List, Optional
from django.utils.text import slugify
from .seo import slugify_title
from django.utils.text import slugify as dj_slugify


_FILENAME_FALLBACK_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-(.+)$')


def slug_from_filename(filename: str, max_len: int = 75) -> str:
	if not filename:
		return ''
	base = filename.rsplit('/', 1)[-1]
	base = base.rsplit('.', 1)[0]
	m = _FILENAME_FALLBACK_RE.match(base)
	if m:
		candidate = m.group(1)
	else:
		candidate = base
	cand = dj_slugify(candidate)[:max_len].strip('-') or candidate[:max_len]
	return cand

def build_jekyll_front_matter(post) -> Dict[str, Any]:
	# Minimale (espandere secondo il vostro schema)
	return {
		# Do not export DB title; title will be taken from body front-matter if present
		"title": "",
		"slug": getattr(post, "slug", ""),
		"date": getattr(post, "date", getattr(post, "published_at", None)),
		"categories": getattr(post, "categories", []) or [],
		"tags": getattr(post, "tags", []) or [],
		"status": getattr(post, "status", "draft"),
	}

def render_markdown_for_export(post) -> str:
	fm = build_jekyll_front_matter(post)
	# If the post body contains front-matter with an explicit title, export it.
	txt = getattr(post, "content", None) or getattr(post, "body", "") or ""
	body_fm = extract_frontmatter(txt)
	if isinstance(body_fm, dict) and body_fm.get("title"):
		fm["title"] = body_fm.get("title")
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


_FM_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", flags=re.S | re.M)


def extract_frontmatter(text: Optional[str]) -> Dict[str, Any]:
	if not text:
		return {}
	m = _FM_RE.search(text)
	if not m:
		return {}
	try:
		return yaml.safe_load(m.group(1)) or {}
	except Exception:
		return {}


def create_categories_from_frontmatter(post, fields: Optional[List[str]] = None, hierarchy: str = "slash") -> List:
	# import locally to avoid circular import with models
	from ..models import Category
	from django.utils.text import slugify

	if fields is None:
		fields = ["categories", "cluster"]
	txt = getattr(post, "content", None) or ""
	fm = extract_frontmatter(txt)
	cats = []

	# First, prefer explicit 'categories' or provided fields if present
	if fm:
		# Handle special cluster/subcluster shapes
		cluster_val = fm.get("cluster")
		subcluster_val = fm.get("subcluster")

		# If 'cluster' exists and is a mapping (dict), interpret as {cluster: [sub,...]}
		if isinstance(cluster_val, dict):
			for clu, subs in cluster_val.items():
				clu = str(clu).strip()
				if isinstance(subs, (list, tuple)):
					for s in subs:
						if s:
							cats.append(f"{clu}/{str(s).strip()}")
				elif subs:
					cats.append(f"{clu}/{str(subs).strip()}")
				else:
					cats.append(clu)
		# If cluster is a list of cluster names
		elif isinstance(cluster_val, (list, tuple)) and cluster_val:
			for clu in cluster_val:
				if clu:
					cats.append(str(clu).strip())
		# If cluster is a scalar string
		elif isinstance(cluster_val, str) and cluster_val.strip():
			clu = cluster_val.strip()
			# combine with subcluster if present
			if subcluster_val:
				if isinstance(subcluster_val, (list, tuple)):
					for s in subcluster_val:
						if s:
							cats.append(f"{clu}/{str(s).strip()}")
				else:
					cats.append(f"{clu}/{str(subcluster_val).strip()}")
			else:
				cats.append(clu)
		# If only subcluster exists (no cluster), treat subcluster as categories
		elif subcluster_val:
			if isinstance(subcluster_val, (list, tuple)):
				for s in subcluster_val:
					if s:
						cats.append(str(s).strip())
			else:
				cats.append(str(subcluster_val).strip())

		# If still no cats, fall back to generic provided fields (like 'categories')
		if not cats:
			vals = []
			for fld in fields:
				if fld in fm and fm[fld] is not None:
					v = fm[fld]
					if isinstance(v, (list, tuple)) and v:
						vals.extend([str(x).strip() for x in v if x])
					else:
						vals.append(str(v).strip())
			if vals:
				# if multiple values, preserve them separately (they may be independent categories)
				cats.extend(vals if len(vals) > 1 else [vals[0]])

	# fallback: legacy categories line
	if not cats:
		m = re.search(r'(?mi)^categories:\s*(.+)$', txt)
		if m:
			cats = [s.strip() for s in re.split(r"[,;]\s*", m.group(1)) if s.strip()]

	if not cats:
		return []

	# Use new normalized category structure - collect unique (cluster, subcluster) tuples
	category_specs = set()
	
	for raw in cats:
		if hierarchy == "slash":
			parts = [p.strip() for p in re.split(r"\s*/\s*", raw) if p.strip()]
		elif hierarchy == ">":
			parts = [p.strip() for p in re.split(r"\s*>\s*", raw) if p.strip()]
		else:
			parts = [raw.strip()]

		if not parts:
			continue
			
		cluster_name = parts[0]
		cluster_slug = slugify(cluster_name) or 'uncategorized'
		
		if len(parts) == 1:
			# Just cluster, no subcluster - this is a standalone category
			category_specs.add((cluster_slug, cluster_name, None, None))
		elif len(parts) == 2:
			# Cluster + subcluster - create both the cluster and the hierarchical category
			subcluster_name = parts[1]
			subcluster_slug = slugify(subcluster_name)
			full_name = f"{cluster_name}/{subcluster_name}"
			
			# Add both the cluster itself and the cluster/subcluster combination
			category_specs.add((cluster_slug, cluster_name, None, None))
			category_specs.add((cluster_slug, cluster_name, subcluster_slug, full_name))
		else:
			# For deeper hierarchies, just take first two levels for now
			subcluster_name = parts[1]
			subcluster_slug = slugify(subcluster_name)
			full_name = f"{cluster_name}/{subcluster_name}"
			
			category_specs.add((cluster_slug, cluster_name, None, None))
			category_specs.add((cluster_slug, cluster_name, subcluster_slug, full_name))

	# Bulk create categories using the new normalized structure
	created_objs = []
	
	for cluster_slug, cluster_name, subcluster_slug, full_name in category_specs:
		display_name = full_name if full_name else cluster_name
		
		# Create backwards-compatible slug for the slug field
		if subcluster_slug:
			compat_slug = f"{cluster_slug}-{subcluster_slug}"
		else:
			compat_slug = cluster_slug
		
		try:
			obj, created = Category.objects.get_or_create(
				site=post.site,
				cluster_slug=cluster_slug,
				subcluster_slug=subcluster_slug,
				defaults={
					'name': display_name,
					'slug': compat_slug,  # Keep for backwards compatibility
				}
			)
			created_objs.append(obj)
		except Exception as e:
			# Log the error but continue processing
			import logging
			logger = logging.getLogger(__name__)
			logger.warning(f"Failed to create category {cluster_slug}/{subcluster_slug}: {e}")

	# assign unique categories to post
	if created_objs:
		unique = []
		seen = set()
		for o in created_objs:
			if o and o.pk and o.pk not in seen:
				unique.append(o)
				seen.add(o.pk)
		if unique:
			# Get current categories to avoid duplicates
			current_category_ids = set(post.categories.values_list('id', flat=True))
			categories_to_add = [cat for cat in unique if cat.id not in current_category_ids]
			
			if categories_to_add:
				post.categories.add(*categories_to_add)  # Add new categories without removing existing ones

	return created_objs

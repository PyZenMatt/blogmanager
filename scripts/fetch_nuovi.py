import os
import requests
import yaml
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
API_URL = os.environ.get("API_URL", "https://pyzenmatt.pythonanywhere.com/api/blog/posts/")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(ROOT_DIR, "_posts"))
SITE_DOMAIN = os.environ.get("SITE_DOMAIN")  # es: https://messymind.it
TOKEN = os.environ.get("API_TOKEN")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Trova tutti gli slug già presenti in _posts
existing_slugs = set()
for fname in os.listdir(OUTPUT_DIR):
    if fname.endswith(".md") and not fname.startswith("."):
        # Jekyll: YYYY-MM-DD-slug.md
        parts = fname.split("-", 3)
        if len(parts) == 4:
            slug = parts[3][:-3]  # rimuove .md
            existing_slugs.add(slug)

params = {}
if SITE_DOMAIN:
    params['site'] = SITE_DOMAIN

headers = {"Authorization": f"Token {TOKEN}"} if TOKEN else {}
print(f"Fetching NEW posts from {API_URL} for site: {SITE_DOMAIN or 'ALL'}")
resp = requests.get(API_URL, params=params, headers=headers)
resp.raise_for_status()
data = resp.json()

new_count = 0
for post in data.get('results', []):
    if post['slug'] in existing_slugs:
        continue  # Salta post già presenti
    # Frontmatter YAML con parametri SEO/social
    frontmatter = {
        'title': post['title'],
        'date': post['published_at'],
        'author': post['author']['name'] if post['author'] else None,
        'categories': [cat['slug'] for cat in post['categories']],
        'tags': [tag['slug'] for tag in post['tags']],
        'slug': post['slug'],
        'canonical_url': post.get('canonical_url'),
        'meta_title': post.get('meta_title'),
        'meta_description': post.get('meta_description'),
        'meta_keywords': post.get('meta_keywords'),
        'og_title': post.get('og_title'),
        'og_description': post.get('og_description'),
        'og_image': post.get('og_image_url'),
        'noindex': post.get('noindex', False),
    }
    comments = post.get('comments', [])
    if comments:
        frontmatter['comments'] = [
            {
                'author': c['author_name'],
                'email': c['author_email'],
                'text': c['text'],
                'created_at': c['created_at'],
            }
            for c in comments
        ]
    pub_date = datetime.fromisoformat(post['published_at'].replace('Z', '+00:00'))
    filename = f"{pub_date.strftime('%Y-%m-%d')}-{post['slug']}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('---\n')
        yaml.dump(frontmatter, f, allow_unicode=True, sort_keys=False)
        f.write('---\n\n')
        f.write(post['content'])
    print(f"Wrote new post: {filepath}")
    new_count += 1
print(f"Done. {new_count} new post(s) written.")

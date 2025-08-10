import os
import sys
import argparse
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

parser = argparse.ArgumentParser(description="Aggiorna post selezionati per slug o ID (da argomento o file)")
parser.add_argument('--slug', nargs='*', help='Uno o più slug')
parser.add_argument('--id', nargs='*', type=int, help='Uno o più ID')
parser.add_argument('--slug-file', help='File con uno slug per riga')
parser.add_argument('--id-file', help='File con un ID per riga')
args = parser.parse_args()

slugs = set(args.slug or [])
ids = set(args.id or [])

if args.slug_file:
    with open(args.slug_file, 'r', encoding='utf-8') as f:
        slugs.update(line.strip() for line in f if line.strip())
if args.id_file:
    with open(args.id_file, 'r', encoding='utf-8') as f:
        ids.update(int(line.strip()) for line in f if line.strip())

if not slugs and not ids:
    print("Devi specificare almeno uno slug o ID (via argomento o file)")
    sys.exit(1)

params = {}
if SITE_DOMAIN:
    params['site'] = SITE_DOMAIN
if slugs:
    params['slug__in'] = ','.join(slugs)
if ids:
    params['id__in'] = ','.join(str(i) for i in ids)

headers = {"Authorization": f"Token {TOKEN}"} if TOKEN else {}
print(f"Fetching SELECTED posts from {API_URL} for slugs: {slugs} and ids: {ids}")
resp = requests.get(API_URL, params=params, headers=headers)
resp.raise_for_status()
data = resp.json()

sel_count = 0
for post in data.get('results', []):
    if slugs and post['slug'] not in slugs:
        continue
    if ids and post['id'] not in ids:
        continue
    frontmatter = {
        'title': post['title'],
        'date': post['published_at'],
        'author': post['author']['name'] if post['author'] else None,
        'categories': [cat['slug'] for cat in post['categories']],
        'site': post['site']['domain'],
        'slug': post['slug'],
        'published': post['is_published'],
        'updated_at': post['updated_at'],
        'seo_title': post.get('seo_title'),
        'background': post.get('background'),
        'tags': post.get('tags'),
        'description': post.get('description'),
        'keywords': post.get('keywords'),
        'canonical_url': post.get('canonical_url'),
        'alt': post.get('alt'),
        'og_type': post.get('og_type'),
        'og_title': post.get('og_title'),
        'og_description': post.get('og_description'),
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
    print(f"Wrote selected post: {filepath}")
    sel_count += 1

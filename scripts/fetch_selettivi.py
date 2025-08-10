
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

parser = argparse.ArgumentParser(description="Scarica post selettivi dal backend.")
parser.add_argument('--slug', nargs='*', help='Filtra per uno o più slug')
parser.add_argument('--id', nargs='*', type=int, help='Filtra per uno o più ID')
parser.add_argument('--author', help='Filtra per autore (nome o ID)')
parser.add_argument('--category', help='Filtra per categoria (slug o ID)')
parser.add_argument('--from-date', help='Filtra post pubblicati da questa data (YYYY-MM-DD)')
parser.add_argument('--to-date', help='Filtra post pubblicati fino a questa data (YYYY-MM-DD)')
args = parser.parse_args()

params = {}
if SITE_DOMAIN:
    params['site'] = SITE_DOMAIN
if args.slug:
    params['slug__in'] = ','.join(args.slug)
if args.id:
    params['id__in'] = ','.join(str(i) for i in args.id)
if args.author:
    params['author'] = args.author
if args.category:
    params['category'] = args.category
if args.from_date:
    params['published_at__gte'] = args.from_date
if args.to_date:
    params['published_at__lte'] = args.to_date

headers = {"Authorization": f"Token {TOKEN}"} if TOKEN else {}
print(f"Fetching SELECTED posts from {API_URL} with filters: {params}")
resp = requests.get(API_URL, params=params, headers=headers)
resp.raise_for_status()
data = resp.json()

sel_count = 0
for post in data.get('results', []):
    # Se slug specificati, filtra anche lato client (per sicurezza)
    if args.slug and post['slug'] not in args.slug:
        continue
    if args.id and post['id'] not in args.id:
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
print(f"Done. {sel_count} selected post(s) written.")

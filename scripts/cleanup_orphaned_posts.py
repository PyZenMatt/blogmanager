import os
import re
from datetime import datetime
from dotenv import load_dotenv

# Configurazione directory _posts
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir))
load_dotenv()
POSTS_DIR = os.environ.get("OUTPUT_DIR", os.path.join(ROOT_DIR, "_posts"))

# Ottieni lista slug pubblicati dal backend (da un file di cache o da fetch_posts.py)
def get_published_slugs(slugs_file):
    with open(slugs_file, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def extract_slug_from_filename(filename):
    # Jekyll: YYYY-MM-DD-slug.md
    match = re.match(r"\\d{4}-\\d{2}-\\d{2}-(.+)\\.md$", filename)
    return match.group(1) if match else None

def main():
    slugs_file = os.path.join(POSTS_DIR, ".published_slugs")
    if not os.path.exists(slugs_file):
        print(f"File slugs non trovato: {slugs_file}. Esegui prima fetch_posts.py con salvataggio slugs.")
        return
    published_slugs = get_published_slugs(slugs_file)
    files = [f for f in os.listdir(POSTS_DIR) if f.endswith(".md") and not f.startswith(".")]
    deleted = 0
    for fname in files:
        slug = extract_slug_from_filename(fname)
        if slug and slug not in published_slugs:
            path = os.path.join(POSTS_DIR, fname)
            os.remove(path)
            print(f"Removed orphaned file: {fname}")
            deleted += 1
    print(f"Cleanup complete. {deleted} file(s) removed.")

if __name__ == "__main__":
    main()

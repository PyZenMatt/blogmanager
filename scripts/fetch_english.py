import os
from dotenv import load_dotenv
import requests
import yaml

# Carica variabili d'ambiente
load_dotenv()
API_URL = os.getenv("API_URL")
ENGLISH_SITE_DOMAIN = "https://matteoricci.net"  # Puoi anche mettere in .env se vuoi
OUTPUT_DIR = os.getenv("ENGLISH_OUTPUT_DIR", "/percorso/assoluto/del/blog/_posts_en")
API_TOKEN = os.getenv("API_TOKEN")

headers = {"Authorization": f"Token {API_TOKEN}"}
params = {
    "sites": ENGLISH_SITE_DOMAIN,
    "language": "en"
}

response = requests.get(API_URL, headers=headers, params=params)
response.raise_for_status()
posts = response.json()

for post in posts:
    slug = post.get("slug")
    title = post.get("title")
    published_at = post.get("published_at")
    content = post.get("content")
    # Altri campi se necessario

    # YAML front matter
    front_matter = {
        "title": title,
        "date": published_at,
        "slug": slug,
        "language": "en",
        # Aggiungi altri campi se vuoi
    }
    filename = f"{OUTPUT_DIR}/{slug}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.dump(front_matter, f, allow_unicode=True)
        f.write("---\n\n")
        f.write(content)

print(f"Esportati {len(posts)} post in inglese su {ENGLISH_SITE_DOMAIN}")

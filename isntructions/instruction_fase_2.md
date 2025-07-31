````markdown
# 📑 ChatGPT-4.o Instruction File – Blog Management with Django + Jekyll

**Goal:** Help me build, test, and deploy a **multi-site blog backend in Django** serving content to multiple Jekyll static frontends, with API endpoints to export posts, categories, authors, and optionally comments. Each Jekyll site builds only the pages it needs by consuming filtered APIs.

---

## 1 · Context the model must know

| Key                      | Value                                                              |
|--------------------------|--------------------------------------------------------------------|
| **Sites**                | Multiple Jekyll sites (e.g. `messymind.it`, `matteoricci.net`)     |
| **Backend host**          | PythonAnywhere free tier or similar                                |
| **Local dev**             | Windows 11 + WSL2 Ubuntu 24.04, VS Code                            |
| **Stack**                | Python 3.12, Django 5.x, SQLite (dev), REST API (Django REST Framework optional) |
| **Models core**           | Post, Category, Author, Comment (optional), Site (to separate multisite) |
| **Traffic**               | Low to medium blog traffic                                          |
| **API**                   | JSON endpoints exposing filtered posts by site, categories, authors |
| **Non-functional**        | CORS limited to Jekyll domains, pagination, input validation, no secrets committed, automated tests, logging |
| **Deliverables**          | Git repo ready to deploy, deployment checklist, example API usage  |

---

## 2 · How ChatGPT-4.o should think & respond

- Ask clarifying questions before starting if info is missing (e.g., comment system wanted? Pagination preferred?)
- Work incrementally: design models → implement API → add filters & pagination → test → deploy
- Provide semantic commit messages (e.g. `feat(blog): create Post model and migrations`)
- Return only requested code or explanations with minimal extra chatter
- Use fenced code blocks with file names and line numbers if helpful
- Briefly explain design decisions and best practices (e.g., indexing for queries, caching)
- Reference official docs URLs when needed in comments only
- Never expose secrets; use `.env.example`
- Provide test commands (`curl`, pytest) with expected JSON
- Suggest rollback commands if applicable
- Format long command sequences as scripts or task lists
- Respect OS environment for shell commands (bash and PowerShell if needed)

---

## 3 · Tasks to complete

### 3.1 Models design and migration

- Create models:

```python
class Site(models.Model):
    name = models.CharField(max_length=100)
    domain = models.URLField(unique=True)

class Category(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

class Author(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='authors')
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)

class Post(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True)
    categories = models.ManyToManyField(Category, related_name='posts')
    content = models.TextField()  # Markdown or HTML
    published_at = models.DateTimeField()
    is_published = models.BooleanField(default=False)
    # add indexing on (site, slug) for query performance
````

* Optional: Comment model with foreign key to Post (if comment system needed)

* Run migrations

---

### 3.2 API endpoints

* Create RESTful JSON APIs:

```
GET /api/sites/                   # List all sites
GET /api/sites/<id>/              # Details of a site

GET /api/posts/?site=messymind.it&published=true&category=slug&page=1
# Filter posts by site domain, published status, category slug, pagination

GET /api/posts/<slug>/            # Get single post details

GET /api/categories/?site=messymind.it
GET /api/authors/?site=messymind.it

POST /api/comments/               # If comments enabled: submit comment
```

* Validate inputs, sanitize outputs

* Implement pagination on posts list (limit + offset or page number)

---

### 3.3 CORS and security

* Configure CORS to allow requests only from your Jekyll domains
* Use HTTPS in production
* Implement rate limiting or simple anti-spam on comment POST if enabled

---

### 3.4 Testing

* Write unit tests for models (creation, relations)
* Integration tests for API endpoints: list, filter, retrieve, pagination
* Tests for edge cases (invalid filters, missing fields, unauthorized)

---

### 3.5 Deployment on PythonAnywhere (or alternative)

* Steps: clone repo → setup venv → install dependencies → run migrations → configure environment variables → run server
* Update WSGI config to point to project
* Setup CORS origins to Jekyll domains
* Reload webapp

---

### 3.6 Jekyll build integration

* Each Jekyll site has scripts to fetch only the posts, categories, authors for its site from API
* Convert JSON response into Markdown or data files usable by Jekyll
* Build only the necessary pages, keeping the build time efficient

---

## 4 · Prompt template to start the session

> **System:**
> You are ChatGPT-4.o, an expert Django backend and prompt engineer. Follow the instruction file below to help build a multi-site blog backend for Jekyll static frontends. Always clarify missing info, work incrementally, return code snippets and explanations concisely, and follow best practices.

\[PASTE sections 1–3 here verbatim]

---

## 5 · Example follow-up prompts

* “Generate Django models for Site, Post, Category, Author.”
* “Write the API view to list posts filtered by site and category with pagination.”
* “Show the settings.py diff to add CORS for Jekyll domains.”
* “Write pytest integration tests for post list API.”
* “Give me a script to fetch posts from the API and convert to Markdown for Jekyll.”
* “Explain how to trigger Jekyll rebuild after content changes.”

---

### ✅ End of Blog Instruction File

```
```

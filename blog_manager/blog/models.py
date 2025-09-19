
import re
import unicodedata
try:
    from cloudinary_storage.storage import MediaCloudinaryStorage
except Exception:  # pragma: no cover - fallback se lib non disponibile all'import
    class MediaCloudinaryStorage:  # type: ignore
        def __init__(self, *a, **kw):
            pass
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify as dj_slugify, slugify
import os

from .utils.seo import slugify_title
import subprocess


def upload_to_post_image(instance, filename):
    # Path: uploads/<blog_slug>/post-<id>/<filename>
    # Supporta sia Post che PostImage
    if hasattr(instance, "site"):
        site = instance.site
        post_id = instance.id if instance.id else "new"
    elif hasattr(instance, "post"):
        site = instance.post.site
        post_id = instance.post.id if instance.post.id else "new"
    else:
        site = "unknown"
        post_id = "new"
    blog_slug = getattr(site, "slug", str(getattr(site, "id", "unknown")))
    return f"uploads/{blog_slug}/post-{post_id}/{filename}"


class Site(models.Model):
    name = models.CharField(max_length=100)
    domain = models.URLField(unique=True)
    slug = models.SlugField(unique=True, blank=True)
    repo_path = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Percorso working copy locale del repo Jekyll (se vuoto usa BLOG_REPO_BASE/<slug> se esiste)",
    )

    # Repo mapping fields
    repo_owner = models.CharField(
        max_length=100, blank=True, help_text="GitHub owner/org"
    )
    repo_name = models.CharField(
        max_length=100, blank=True, help_text="GitHub repo name"
    )
    default_branch = models.CharField(
        max_length=100, default="main", help_text="Default branch"
    )
    posts_dir = models.CharField(
        max_length=100, default="_posts", help_text="Directory for posts"
    )
    media_dir = models.CharField(
        max_length=100, default="assets/img", help_text="Directory for media"
    )
    base_url = models.URLField(blank=True, help_text="Base URL for published site")

    MEDIA_STRATEGY_CHOICES = [
        ("external", "External URLs (Cloudinary/S3)"),
        ("commit", "Commit assets in repo"),
    ]
    media_strategy = models.CharField(
        max_length=20,
        choices=MEDIA_STRATEGY_CHOICES,
        default="external",
        help_text="How to handle post images: external URLs or commit assets in repo.",
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.default_branch:
            raise ValidationError("default_branch cannot be empty.")
        if self.posts_dir:
            self.posts_dir = self.posts_dir.strip().strip("/")
        if self.media_dir:
            self.media_dir = self.media_dir.strip().strip("/")
        if self.repo_path:
            self.repo_path = self.repo_path.strip()
        if not self.slug:
            self.slug = slugify(self.name) or slugify(self.domain) or "site"

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = slugify(self.name) or slugify(self.domain) or "site"
        if not self.slug:
            base = slugify(self.name) or slugify(self.domain) or f"site{getattr(self,'pk','') or ''}"
            self.slug = base

    # If repo_path not set, attempt to use BLOG_REPO_BASE/<slug> as fallback.
    # If the directory exists we set repo_path. Try to create the fallback
    # directory as a best-effort even in non-DEBUG environments so that
    # automated import/sync operations can proceed on managed hosts.
        try:
            from django.conf import settings

            if not (self.repo_path and str(self.repo_path).strip()):
                blog_base = getattr(settings, "BLOG_REPO_BASE", None)
                if blog_base:
                    candidate = os.path.join(blog_base, self.slug)
                    # If it already exists, use it
                    if os.path.isdir(candidate):
                        self.repo_path = candidate
                    else:
                        # Best-effort create fallback path so imports can write
                        # into a managed location. Do not raise on failure.
                        try:
                            os.makedirs(candidate, exist_ok=True)
                            self.repo_path = candidate
                        except Exception:
                            # ignore creation failures (might be permission issues)
                            pass
        except Exception:
            # if settings not available or any error, continue without setting repo_path
            pass

        super().save(*a, **kw)

        # Ensure a local git working copy exists and origin is configured.
        # If the directory is empty and repo_owner/repo_name are set, try to clone.
        # Otherwise, initialize a git repo and add origin if missing.
        try:
            repo = (self.repo_path or "").strip()
            if repo:
                os.makedirs(repo, exist_ok=True)
                git_dir = os.path.join(repo, ".git")
                remote = None
                if getattr(self, "repo_owner", None) and getattr(self, "repo_name", None):
                    remote = f"https://github.com/{self.repo_owner}/{self.repo_name}.git"
                if not os.path.isdir(git_dir):
                    # If directory appears empty and we have a remote, try to clone
                    try:
                        entries = os.listdir(repo)
                    except Exception:
                        entries = []
                    if (not entries) and remote:
                        try:
                            subprocess.run(["git", "clone", remote, repo], check=True)
                        except Exception:
                            # fallback: init and add origin
                            try:
                                subprocess.run(["git", "init"], cwd=repo, check=True)
                                if remote:
                                    subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, check=False)
                            except Exception:
                                pass
                    else:
                        # non-empty or no remote: ensure git init and origin present if possible
                        try:
                            subprocess.run(["git", "init"], cwd=repo, check=True)
                            if remote:
                                # add origin only if not present
                                rc = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo, capture_output=True, text=True)
                                if rc.returncode != 0:
                                    subprocess.run(["git", "remote", "add", "origin", remote], cwd=repo, check=False)
                            # If repository has no commits yet, create an initial commit and attempt to push
                            try:
                                rc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
                                if rc.returncode != 0:
                                    # create a README if the directory is empty, otherwise add existing files
                                    try:
                                        entries = os.listdir(repo)
                                    except Exception:
                                        entries = []
                                    if not entries:
                                        with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
                                            fh.write(f"# {self.slug}\n")
                                        subprocess.run(["git", "add", "README.md"], cwd=repo, check=False)
                                    else:
                                        subprocess.run(["git", "add", "--all"], cwd=repo, check=False)
                                    # commit (allow failure)
                                    try:
                                                # ensure minimal git config so commit can succeed
                                                subprocess.run(["git", "config", "user.name", os.environ.get('GIT_COMMIT_NAME','blog-manager')], cwd=repo, check=False)
                                                subprocess.run(["git", "config", "user.email", os.environ.get('GIT_COMMIT_EMAIL','blog-manager@example.com')], cwd=repo, check=False)
                                                # set initial branch name to configured branch
                                                initial_branch = os.environ.get('GIT_BRANCH', 'main')
                                                subprocess.run(["git", "checkout", "-b", initial_branch], cwd=repo, check=False)
                                                subprocess.run(["git", "commit", "-m", "chore(blog): initial commit"], cwd=repo, check=True)
                                    except Exception:
                                        # commit may fail if user identity is not configured; ignore
                                        pass
                                    # attempt push: prefer HTTPS push URL with token if available
                                    try:
                                                if remote and remote.startswith("https://"):
                                                    token = os.environ.get("GIT_TOKEN")
                                                    user = os.environ.get("GIT_USERNAME", "x-access-token")
                                                    if token:
                                                        push_url = remote.replace("https://", f"https://{user}:{token}@")
                                                        subprocess.run(["git", "push", push_url, f"HEAD:{initial_branch}"], cwd=repo, check=False)
                                                    else:
                                                        subprocess.run(["git", "push", "origin", f"HEAD:{initial_branch}"] , cwd=repo, check=False)
                                                else:
                                                    subprocess.run(["git", "push", "origin", f"HEAD:{initial_branch}"], cwd=repo, check=False)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        except Exception:
                            pass
        except Exception:
            # best-effort only; don't block save on git failures
            pass

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["id"]


class Category(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=180, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site})"

    class Meta:
        unique_together = (("site", "slug"),)
        indexes = [
            models.Index(fields=["site", "slug"]),
        ]
        ordering = ["id"]


class Author(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="authors")
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    slug = models.SlugField()
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=180, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site})"

    class Meta:
        ordering = ["id"]
        unique_together = (("site", "slug"),)
        indexes = [
            models.Index(fields=["site", "slug"]),
        ]


class Post(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=200)
    # Deve restare max_length=200; avoid MySQL-specific collation on SQLite
    slug = models.SlugField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True)
    categories = models.ManyToManyField(Category, related_name="posts", blank=True)
    content = models.TextField()  # Markdown o HTML
    published_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    LANGUAGE_CHOICES = [
        ("it", "Italiano"),
        ("en", "English"),
    ]
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default="it",
        help_text="Lingua dell'articolo",
    )

    # Editorial workflow fields
    # Allineato alla migration 0009: niente NULL (evita errori "Column 'exported_hash' cannot be null")
    # Usiamo default=""; resta indicizzato per lookup rapido
    exported_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Hash dell'export (contenuto/front matter) per rilevare cambiamenti lato Jekyll."
    )
    last_exported_at = models.DateTimeField(null=True, blank=True)
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("review", "Review"),
        ("published", "Published"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    reviewed_by = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_posts",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Campi aggiuntivi per front matter ricco
    background = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "Incolla qui l'URL Cloudinary dell'immagine di background. Es: "
            "https://res.cloudinary.com/dkoc4knvv/image/upload/v1/…"
        ),
        default="https://res.cloudinary.com/dkoc4knvv/image/upload/v1/",
    )
    tags = models.TextField(
        blank=True, help_text="Separare i tag con virgola o newline"
    )
    description = models.TextField(blank=True)
    keywords = models.TextField(
        blank=True, help_text="Separare le keyword con virgola o newline"
    )
    canonical_url = models.URLField(blank=True)
    # OpenGraph / noindex fields removed — content-based markdown only now
    # Osservabilità export/build
    export_status = models.CharField(
        max_length=16,
        choices=[("success", "Success"), ("failed", "Failed"), ("pending", "Pending")],
        default="pending",
        help_text="Stato export/build",
    )
    last_pages_build_url = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        help_text="URL build/errore ultima pubblicazione",
    )
    last_export_path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Percorso ultimo file esportato su Jekyll",
    )

    # Audit pubblicazione
    repo_path = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Percorso del file nel repo Jekyll (_posts/....md)",
    )
    last_commit_sha = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="SHA dell'ultimo commit di pubblicazione",
    )
    last_published_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Hash dell'ultimo contenuto pubblicato (front-matter + body)",
    )
    exported_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp dell'ultima esportazione",
    )

    # Compat alias: exporter usa export_hash ma il campo DB si chiama exported_hash
    @property
    def export_hash(self):  # pragma: no cover - semplice alias
        return getattr(self, 'exported_hash', '')

    @export_hash.setter
    def export_hash(self, value):  # pragma: no cover
        self.exported_hash = value

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.status == "published" and (not self.published_at):
            raise ValidationError("published_at is required when status is published.")
        if self.status == "published" and not self.is_published:
            raise ValidationError("is_published must be True when status is published.")
        if self.status == "review" and not self.reviewed_by:
            raise ValidationError("reviewed_by is required when status is review.")
        # Export safety: require working copy present (direct or fallback) when published
        if self.status == "published":
            site = getattr(self, "site", None)
            if not site:
                raise ValidationError({"site": "Site richiesto per pubblicare."})
            repo_path = (site.repo_path or "").strip()
            from django.conf import settings
            fallback = None
            if not repo_path and getattr(settings, "BLOG_REPO_BASE", None):
                fallback = os.path.join(settings.BLOG_REPO_BASE, site.slug)
            if repo_path and not os.path.isdir(repo_path):
                raise ValidationError({"site": f"repo_path inesistente: {repo_path}"})
            if (not repo_path) and fallback and not os.path.isdir(fallback):
                # Best-effort: try to create the fallback directory so sync can proceed.
                try:
                    os.makedirs(fallback, exist_ok=True)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        "Could not create fallback repo path %s: %s", fallback, e
                    )
                    raise ValidationError({
                        "site": "Configura repo_path o crea directory fallback BLOG_REPO_BASE/<slug>."
                    })

                # If creation succeeded, persist it on the site (best-effort)
                try:
                    site.repo_path = fallback
                    site.save()
                except Exception:
                    # ignore persistence failures; directory exists and that's sufficient
                    pass

                # final check: if still not a directory, raise
                if not os.path.isdir(fallback):
                    raise ValidationError({
                        "site": "Configura repo_path o crea directory fallback BLOG_REPO_BASE/<slug>."
                    })

    # imports now at top-level

    @staticmethod
    def _normalize(s: str) -> str:
        if not s:
            return s
        s = re.sub(r"[\x00\uD800-\uDFFF]", "", s)  # null bytes + surrogati
        try:
            s = unicodedata.normalize("NFKD", s)
        except Exception:
            pass
        return s

    @classmethod
    def safe_slugify(cls, site_id: int, title: str, base_slug: str = None, max_len: int = 200) -> str:
        base = base_slug or dj_slugify(cls._normalize(title)) or "post"
        base = base[:max_len].strip("-")
        candidate = base
        i = 2
        while cls.objects.filter(site_id=site_id, slug=candidate).exists():
            suffix = f"-{i}"
            cut = max_len - len(suffix)
            candidate = f"{base[:cut].rstrip('-')}{suffix}"
            i += 1
        return candidate

    def save(self, *args, **kwargs):
        # Autogenerazione slug se mancante o vuoto
        site_id = self.site.pk
        if not self.slug:
            self.slug = self.safe_slugify(site_id=site_id, title=self.title)
        else:
            self.slug = self._normalize(self.slug)
            self.slug = dj_slugify(self.slug)[:200].strip("-") or "post"
        # Normalizza campi di pubblicazione prima della validazione
        if self.status == "published":
            # Se manca published_at lo settiamo ora
            if not self.published_at:
                self.published_at = timezone.now()
            # Allineiamo il flag legacy is_published
            if not self.is_published:
                self.is_published = True
        else:
            # Manteniamo coerenza: se non published lo stato booleano può restare False
            if self.is_published and self.status != "published":
                # Evita incoerenze silenziose: lasciamo is_published così com'è solo se user l'ha impostato.
                pass
        self.full_clean()
        from django.db import transaction
        with transaction.atomic():
            super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["site", "slug"], name="uniq_site_slug"),
        ]
        indexes = [
            models.Index(fields=["site", "slug"]),
        ]
        ordering = ["-published_at", "-id"]

    def __str__(self):
        return f"{self.title} ({self.site})"


class ExportJob(models.Model):
    EXPORT_STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("pending", "Pending"),
    ]

    ACTION_CHOICES = [
        ("publish", "Publish"),
        ("refresh", "Refresh/Check"),
        ("delete_db_only", "Delete DB-only"),
        ("delete_repo_and_db", "Delete Repo + DB"),
    ]

    post = models.ForeignKey(
        "Post", on_delete=models.CASCADE, related_name="export_jobs"
    )
    exported_at = models.DateTimeField(default=timezone.now)
    commit_sha = models.CharField(max_length=64, blank=True, null=True)
    repo_url = models.URLField(max_length=255, blank=True, null=True)
    branch = models.CharField(max_length=64, blank=True, null=True)
    path = models.CharField(max_length=255, blank=True, null=True)
    export_status = models.CharField(
        max_length=16, choices=EXPORT_STATUS_CHOICES, default="pending"
    )
    # Normalized action describing what triggered this job
    action = models.CharField(max_length=32, choices=ACTION_CHOICES, blank=True, null=True)
    # Human-readable message/details about the job outcome (e.g. "no_changes", "drift_absent")
    message = models.TextField(blank=True, null=True)

    def __str__(self):
        pid = getattr(self.post, "pk", None)
        return f"ExportJob for Post {pid} ({self.export_status})"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post}"

    class Meta:
        ordering = ["id"]


class ExportAudit(models.Model):
    """Record runs and actions performed by sync/backup/delete operations."""
    run_id = models.CharField(max_length=64, db_index=True)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=64)  # e.g. sync:dry-run, sync:apply, delete:dry-run
    summary = models.JSONField(blank=True, null=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ExportAudit {self.run_id} {self.action}"


class MigrationLog(models.Model):
    """Record admin-triggered migration runs."""
    run_at = models.DateTimeField(auto_now_add=True)
    user = models.CharField(max_length=150, blank=True, null=True)
    command = models.CharField(max_length=200)
    output = models.TextField(blank=True, null=True)
    success = models.BooleanField(default=False)

    class Meta:
        ordering = ["-run_at"]

    def __str__(self):
        return f"Migration {self.command} at {self.run_at} ({'ok' if self.success else 'fail'})"


# Immagini multiple per post
class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        upload_to=upload_to_post_image, storage=MediaCloudinaryStorage()
    )
    caption = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Immagine per {self.post.title}"

    class Meta:
        ordering = ["id"]


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    posts = models.ManyToManyField("Post", related_name="tagged_posts", blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["slug"]


@receiver(pre_save, sender=Post)
def post_autofill(sender, instance, **kwargs):
    # Mantieni solo logica minima: genera slug se mancante.
    if not instance.slug and instance.title:
        instance.slug = slugify_title(instance.title)

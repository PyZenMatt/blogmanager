from django.db import models
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .utils.seo import slugify_title, extract_plain, meta_defaults

def upload_to_post_image(instance, filename):
    # Path: uploads/<blog_slug>/post-<id>/<filename>
    # Supporta sia Post che PostImage
    if hasattr(instance, 'site'):
        site = instance.site
        post_id = instance.id if instance.id else 'new'
    elif hasattr(instance, 'post'):
        site = instance.post.site
        post_id = instance.post.id if instance.post.id else 'new'
    else:
        site = 'unknown'
        post_id = 'new'
    blog_slug = getattr(site, 'slug', str(getattr(site, 'id', 'unknown')))
    return f"uploads/{blog_slug}/post-{post_id}/{filename}"

from django.db import models

class Site(models.Model):
    name = models.CharField(max_length=100)
    domain = models.URLField(unique=True)

    # Repo mapping fields
    repo_owner = models.CharField(max_length=100, blank=True, help_text="GitHub owner/org")
    repo_name = models.CharField(max_length=100, blank=True, help_text="GitHub repo name")
    default_branch = models.CharField(max_length=100, default="main", help_text="Default branch")
    posts_dir = models.CharField(max_length=100, default="_posts", help_text="Directory for posts")
    media_dir = models.CharField(max_length=100, default="assets/img", help_text="Directory for media")
    base_url = models.URLField(blank=True, help_text="Base URL for published site")

    MEDIA_STRATEGY_CHOICES = [
        ("external", "External URLs (Cloudinary/S3)"),
        ("commit", "Commit assets in repo")
    ]
    media_strategy = models.CharField(
        max_length=20,
        choices=MEDIA_STRATEGY_CHOICES,
        default="external",
        help_text="How to handle post images: external URLs or commit assets in repo."
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.default_branch:
            raise ValidationError("default_branch cannot be empty.")
        # Normalize paths
        if self.posts_dir:
            self.posts_dir = self.posts_dir.strip().strip('/')
        if self.media_dir:
            self.media_dir = self.media_dir.strip().strip('/')

    def __str__(self):
        return self.name

class Category(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=180, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site})"

class Author(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='authors')
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    slug = models.SlugField(unique=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=180, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site})"

class Post(models.Model):

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True)
    categories = models.ManyToManyField(Category, related_name='posts')
    content = models.TextField()  # Markdown o HTML
    published_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    LANGUAGE_CHOICES = [
        ("it", "Italiano"),
        ("en", "English"),
    ]
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="it", help_text="Lingua dell'articolo")

    # Editorial workflow fields
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("review", "Review"),
        ("published", "Published"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    reviewed_by = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_posts')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Campi aggiuntivi per front matter ricco
    seo_title = models.CharField(max_length=200, blank=True)
    background = models.CharField(
        max_length=200,
        blank=True,
        help_text="Incolla qui l'URL Cloudinary dell'immagine di background. Es: https://res.cloudinary.com/dkoc4knvv/image/upload/v1/…",
        default="https://res.cloudinary.com/dkoc4knvv/image/upload/v1/"
    )
    tags = models.TextField(blank=True, help_text="Separare i tag con virgola o newline")
    description = models.TextField(blank=True)
    keywords = models.TextField(blank=True, help_text="Separare le keyword con virgola o newline")
    canonical_url = models.URLField(blank=True)
    og_title = models.CharField(max_length=100, blank=True)
    og_description = models.CharField(max_length=200, blank=True)
    og_image_url = models.URLField(blank=True)
    noindex = models.BooleanField(default=False)
        # Osservabilità export/build
    export_status = models.CharField(max_length=16, choices=[("success", "Success"), ("failed", "Failed"), ("pending", "Pending")], default="pending", help_text="Stato export/build")
    last_pages_build_url = models.URLField(max_length=255, blank=True, null=True, help_text="URL build/errore ultima pubblicazione")

    def clean(self):
        from django.core.exceptions import ValidationError
        # Only staff can publish
        if self.status == "published" and (not self.published_at):
            raise ValidationError("published_at is required when status is published.")
        if self.status == "published" and not self.is_published:
            raise ValidationError("is_published must be True when status is published.")
        if self.status == "review" and not self.reviewed_by:
            raise ValidationError("reviewed_by is required when status is review.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = (('site', 'slug'),)
        indexes = [
            models.Index(fields=['site', 'slug']),
        ]

    def __str__(self):
        return f"{self.title} ({self.site})"

        class ExportJob(models.Model):
            EXPORT_STATUS_CHOICES = [
                ("success", "Success"),
                ("failed", "Failed"),
                ("pending", "Pending"),
            ]

            post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='export_jobs')
            exported_at = models.DateTimeField(default=timezone.now)
            commit_sha = models.CharField(max_length=64, blank=True, null=True)
            repo_url = models.URLField(max_length=255, blank=True, null=True)
            branch = models.CharField(max_length=64, blank=True, null=True)
            path = models.CharField(max_length=255, blank=True, null=True)
            export_status = models.CharField(max_length=16, choices=EXPORT_STATUS_CHOICES, default="pending")
            export_error = models.TextField(blank=True, null=True)

            def __str__(self):
                return f"ExportJob for Post {self.post_id} ({self.export_status})"

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post}"


# Immagini multiple per post
class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=upload_to_post_image, storage=MediaCloudinaryStorage())
    caption = models.CharField(max_length=200, blank=True)


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Immagine per {self.post.title}"

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    posts = models.ManyToManyField('Post', related_name='tagged_posts', blank=True)

    def __str__(self):
        return self.name

@receiver(pre_save, sender=Post)
def post_autofill(sender, instance, **kwargs):
    if not instance.slug and instance.title:
        instance.slug = slugify_title(instance.title)
    body_plain = extract_plain(instance.content or '')
    cats = [c.name for c in instance.categories.all()] if instance.pk else []
    tags = [t.name for t in instance.tags.all()] if instance.pk else []
    if not instance.meta_title or not instance.meta_description or not instance.meta_keywords:
        mt, md, mk = meta_defaults(instance.title or '', body_plain, cats, tags)
        instance.meta_title = instance.meta_title or mt
        instance.meta_description = instance.meta_description or md
        instance.meta_keywords = instance.meta_keywords or mk
    if not instance.og_title:
        instance.og_title = instance.meta_title or instance.title or ''
    if not instance.og_description:
        instance.og_description = instance.meta_description or ''



from django.db import models
from cloudinary_storage.storage import MediaCloudinaryStorage

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

    def __str__(self):
        return self.name

class Category(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return f"{self.name} ({self.site})"

class Author(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='authors')
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return f"{self.name} ({self.site})"

class Post(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True)
    categories = models.ManyToManyField(Category, related_name='posts')
    content = models.TextField()  # Markdown o HTML
    published_at = models.DateTimeField()
    is_published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

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
    alt = models.CharField(max_length=200, blank=True)
    og_type = models.CharField(max_length=50, blank=True)
    og_title = models.CharField(max_length=200, blank=True)
    og_description = models.TextField(blank=True)

    class Meta:
        unique_together = (('site', 'slug'),)
        indexes = [
            models.Index(fields=['site', 'slug']),
        ]

    def __str__(self):
        return f"{self.title} ({self.site})"


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

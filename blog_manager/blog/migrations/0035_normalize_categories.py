# Generated migration to normalize category model
from django.db import migrations, models
import django.db.models.deletion


def populate_category_fields(apps, schema_editor):
    """Populate the new cluster_slug and subcluster_slug fields and deduplicate"""
    Category = apps.get_model('blog', 'Category')
    Post = apps.get_model('blog', 'Post')
    
    # Find all categories and group by (site, normalized_slug)
    # where normalized_slug removes the numeric suffixes
    import re
    from collections import defaultdict
    from django.utils.text import slugify
    
    categories_by_key = defaultdict(list)
    
    for category in Category.objects.all().select_related('site'):
        # Parse cluster/subcluster from name
        name = category.name or category.slug or ''
        
        if '/' in name:
            cluster, subcluster = name.split('/', 1)
            cluster = cluster.strip()
            subcluster = subcluster.strip()
        else:
            # For existing categories like "django-2", "django-3", extract base name
            cluster = name.strip()
            # Remove numeric suffixes to find the true cluster name
            cluster = re.sub(r'-\d+$', '', cluster)
            subcluster = None
            
        # Normalize to slugs
        cluster_slug = slugify(cluster) or 'uncategorized'
        subcluster_slug = slugify(subcluster) if subcluster else None
        
        # Group by (site_id, cluster_slug, subcluster_slug) 
        key = (category.site_id, cluster_slug, subcluster_slug)
        categories_by_key[key].append(category)
    
    # For each group of duplicates, keep the one with the lowest ID
    # and repoint all Post M2M relationships to it
    for key, category_group in categories_by_key.items():
        site_id, cluster_slug, subcluster_slug = key
        
        if len(category_group) <= 1:
            # Single category, just populate the new fields
            category = category_group[0]
            category.cluster_slug = cluster_slug
            category.subcluster_slug = subcluster_slug
            category.save(update_fields=['cluster_slug', 'subcluster_slug'])
            continue
            
        # Multiple categories - need deduplication
        # Sort by ID to get the canonical category (lowest ID)
        category_group.sort(key=lambda c: c.id)
        canonical_category = category_group[0]
        duplicates = category_group[1:]
        
        print(f"Deduplicating {len(category_group)} categories for {cluster_slug}/{subcluster_slug or 'None'}")
        
        # Set fields on canonical category
        canonical_category.cluster_slug = cluster_slug
        canonical_category.subcluster_slug = subcluster_slug
        canonical_category.save(update_fields=['cluster_slug', 'subcluster_slug'])
        
        # Repoint all posts from duplicates to canonical category
        for duplicate in duplicates:
            # Get all posts that reference this duplicate category
            duplicate_relationships = Post.categories.through.objects.filter(category=duplicate)
            
            for rel in duplicate_relationships:
                # Check if the post already has the canonical category
                existing = Post.categories.through.objects.filter(
                    post=rel.post, 
                    category=canonical_category
                ).exists()
                
                if not existing:
                    # Update the relationship to point to canonical category
                    rel.category = canonical_category
                    rel.save()
                else:
                    # Just delete the duplicate relationship
                    rel.delete()
            
            print(f"  Repointed posts from duplicate category {duplicate.id} to canonical {canonical_category.id}")
        
        # Delete the duplicate categories
        duplicate_ids = [d.id for d in duplicates]
        Category.objects.filter(id__in=duplicate_ids).delete()
        print(f"  Deleted duplicate categories: {duplicate_ids}")


def reverse_populate_category_fields(apps, schema_editor):
    """Reverse migration - not possible to restore duplicates"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '00yy_add_repo_filename'),
    ]

    operations = [
        # Add new fields for normalized structure
        migrations.AddField(
            model_name='category',
            name='cluster_slug',
            field=models.SlugField(default='', help_text='Normalized cluster identifier (e.g., django, frontend)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='category',
            name='subcluster_slug',
            field=models.SlugField(blank=True, null=True, help_text='Optional subcluster identifier (e.g., forms, authentication)'),
        ),
        
        # Populate new fields and deduplicate existing categories
        migrations.RunPython(populate_category_fields, reverse_populate_category_fields),
        
        # Remove old unique constraint (it's actually an index with unique constraint)
        # Django's unique_together creates a unique index, not a constraint object
        # We'll handle this during schema changes
        
        # Add new unique constraint
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(
                fields=['site', 'cluster_slug', 'subcluster_slug'], 
                name='unique_site_cluster_subcluster'
            ),
        ),
        
        # Add index for performance
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['site', 'cluster_slug', 'subcluster_slug'], name='idx_site_cluster_sub'),
        ),
    ]
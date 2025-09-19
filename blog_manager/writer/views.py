from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from blog.models import Post
from blog.services.publish import publish_post
from blog.models import Category
from django.db.models import Q
from blog.utils import extract_frontmatter
import re


class BootstrapLoginView(auth_views.LoginView):
    template_name = "writer/login.html"
    authentication_form = AuthenticationForm
    redirect_authenticated_user = True

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Add Bootstrap classes to widgets
        for name, field in form.fields.items():
            classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (classes + " form-control").strip()
            field.widget.attrs.setdefault("autocomplete", name)
        form.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        form.fields["password"].widget.attrs.setdefault("placeholder", "Password")
        return form

    def form_valid(self, form):
        # Handle "remember me": if unchecked, session expires on browser close
        remember = self.request.POST.get("remember") == "on"
        super().form_valid(form)
        if not remember:
            self.request.session.set_expiry(0)  # expire at browser close
        # Redirect to post list after login
        return redirect("writer:post_list")


class BootstrapLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("writer:login")

    def get_next_page(self):
        base = super().get_next_page()
        # Add flag to show "logged out" banner in login
        return f"{base}?logged_out=1" if base else None


@login_required
def post_new(request):
    return render(request, "writer/post_new.html")


@login_required
def post_edit(request, id):
    return render(request, "writer/post_edit.html", {"post_id": id})


@login_required
def taxonomy(request):
    return render(request, "writer/taxonomy.html")


@login_required
def category_page(request, cat_id: int):
    cat = get_object_or_404(Category, pk=cat_id)
    # subcategories are categories with name like 'CategoryName/Sub'
    prefix = cat.name + '/'
    subcats = Category.objects.filter(site=cat.site, name__startswith=prefix).order_by('name')
    # Build grouped posts per subcategory and parent-only posts
    posts_in_subcats = Post.objects.filter(categories__in=subcats).distinct()
    grouped = []
    for s in subcats:
        qs = posts_in_subcats.filter(categories=s).distinct().order_by('-published_at')
        # compute short label for display (part after the first slash)
        if '/' in s.name:
            short = s.name.split('/', 1)[1]
        else:
            short = s.name
        grouped.append((s, qs, short))

    parent_posts = Post.objects.filter(categories=cat).distinct().exclude(pk__in=posts_in_subcats).order_by('-published_at')

    total_grouped_count = sum(qs.count() for (_s, qs, _short) in grouped)

    return render(request, 'writer/category_listing.html', {
        'category': cat,
        'subcategories': subcats,
        'grouped_posts': grouped,
        'parent_posts': parent_posts,
        'total_grouped_count': total_grouped_count,
    })


@login_required
def subcluster_page(request, cat_id: int, sub_id: int):
    # cat_id is parent category id, sub_id is the subcategory id
    parent = get_object_or_404(Category, pk=cat_id)
    sub = get_object_or_404(Category, pk=sub_id, site=parent.site)
    # posts in this subcategory
    posts_qs = Post.objects.filter(categories=sub).order_by('-published_at')
    # If no posts found via M2M, try to find posts that reference this subcluster in front-matter
    posts_pks = list(posts_qs.values_list('pk', flat=True))
    if not posts_pks:
        extra_pks = []
        # scan posts in same site and check front-matter for matching category/subcategory
        candidates = Post.objects.filter(site=parent.site).exclude(pk__in=posts_pks)
        # `sub.name` is stored as 'Parent/Sub'; extract the sub part for matching
        if '/' in sub.name:
            sub_part = sub.name.split('/', 1)[1]
        else:
            sub_part = sub.name
        target_full = sub.name  # full stored name
        target_sub = sub_part  # short subcluster name
        for p in candidates:
            try:
                fm = extract_frontmatter(getattr(p, 'content', '') or '')
            except Exception:
                fm = {}
            matched = False
            # check explicit 'categories'
            cats = fm.get('categories')
            if cats:
                if isinstance(cats, (list, tuple)):
                    for c in cats:
                        if not c:
                            continue
                        if str(c).strip() in (target_full, target_sub):
                            matched = True
                            break
                else:
                    if str(cats).strip() in (target_full, target_sub):
                        matched = True
            # check cluster/subcluster fields
            if not matched:
                cluster_val = fm.get('cluster')
                sub_val = fm.get('subcluster')
                # cluster can be mapping, list or scalar
                if isinstance(cluster_val, dict):
                    for clu, subs in cluster_val.items():
                        clu = str(clu).strip()
                        if isinstance(subs, (list, tuple)):
                            for s in subs:
                                if s and (f"{clu}/{s}" == target_full or str(s).strip() == target_sub):
                                    matched = True
                                    break
                            if matched:
                                break
                        elif subs and (f"{clu}/{subs}" == target_full or str(subs).strip() == target_sub):
                            matched = True
                            break
                elif isinstance(cluster_val, (list, tuple)) and cluster_val:
                    for clu in cluster_val:
                        if clu and (str(clu).strip() == target_sub or str(clu).strip() == target_full):
                            matched = True
                            break
                elif isinstance(cluster_val, str) and cluster_val.strip():
                    clu = cluster_val.strip()
                    if sub_val:
                        if isinstance(sub_val, (list, tuple)):
                            for s in sub_val:
                                if s and (f"{clu}/{s}" == target_full or str(s).strip() == target_sub):
                                    matched = True
                                    break
                        else:
                            if f"{clu}/{sub_val}" == target_full or str(sub_val).strip() == target_sub:
                                matched = True
                    else:
                        if clu == target_sub or clu == target_full:
                            matched = True
                elif sub_val:
                    # only subcluster provided
                    if isinstance(sub_val, (list, tuple)):
                        for s in sub_val:
                            if s and str(s).strip() in (target_full, target_sub):
                                matched = True
                                break
                    else:
                        if str(sub_val).strip() in (target_full, target_sub):
                            matched = True
            if matched:
                extra_pks.append(p.pk)
            else:
                # also check front-matter tags and Post.tags text field for matches
                tags_fm = fm.get('tags') if isinstance(fm, dict) else None
                if tags_fm:
                    if isinstance(tags_fm, (list, tuple)):
                        for t in tags_fm:
                            if t and str(t).strip() in (target_full, target_sub):
                                extra_pks.append(p.pk)
                                break
                    else:
                        if str(tags_fm).strip() in (target_full, target_sub):
                            extra_pks.append(p.pk)
                            continue
                # Post.tags is a free text field; split by comma/newline and check tokens
                tfield = (getattr(p, 'tags', '') or '')
                if tfield:
                    tokens = re.split(r"[,\n\r]+", tfield)
                    for tok in tokens:
                        if tok and tok.strip() in (target_full, target_sub):
                            extra_pks.append(p.pk)
                            break
        if extra_pks:
            posts_qs = Post.objects.filter(pk__in=extra_pks).order_by('-published_at')
        else:
            posts_qs = posts_qs
    posts = posts_qs
    # siblings (other subcategories in same parent)
    prefix = parent.name + '/'
    siblings = Category.objects.filter(site=parent.site, name__startswith=prefix).exclude(pk=sub.pk).order_by('name')
    return render(request, 'writer/category_listing.html', {
        'category': parent,
        'subcategory': sub,
        'posts': posts,
        'subcategories': siblings,
    })


@login_required
def post_list(request):
    return render(request, "writer/posts_list.html")


@login_required
def post_list_mobile(request):
    return render(request, "writer/posts_list.html", {"mobile": True})


@login_required
def republish(request, id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")
    post = get_object_or_404(Post, pk=id)
    try:
        res = publish_post(post)
    except Exception as e:
        return HttpResponse(f"Publish failed: {e}", status=500)
    return redirect("writer:post_list")


@login_required
def post_new_mobile(request):
    return render(request, "writer/post_new.html", {"mobile": True})


@login_required
def post_edit_mobile(request, id):
    return render(request, "writer/post_edit.html", {"post_id": id, "mobile": True})

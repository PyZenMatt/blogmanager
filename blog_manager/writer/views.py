from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from blog.models import Post
from blog.services.publish import publish_post


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
def post_list(request):
    return render(request, "writer/posts_list.html")


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

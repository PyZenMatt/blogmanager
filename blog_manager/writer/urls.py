from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from .views import BootstrapLoginView, BootstrapLogoutView
from . import views

app_name = "writer"

urlpatterns = [
    path("login/", BootstrapLoginView.as_view(), name="login"),
    path("logout/", BootstrapLogoutView.as_view(), name="logout"),
    path(
        "new/",
        views.post_new,
        name="post_new",  # Already protected by @login_required
    ),
    path("taxonomy/", views.taxonomy, name="taxonomy"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="writer/password_reset_form.html",
            email_template_name="writer/password_reset_email.txt",
            subject_template_name="writer/password_reset_subject.txt",
            success_url=reverse_lazy("writer:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="writer/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="writer/password_reset_confirm.html",
            success_url=reverse_lazy("writer:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="writer/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("posts/", views.post_list, name="post_list"),
    path("edit/<int:id>/", views.post_edit, name="post_edit"),
]

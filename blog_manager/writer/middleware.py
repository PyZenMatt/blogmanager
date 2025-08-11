from time import time

from django.core.cache import cache
from django.shortcuts import render

MAX_ATTEMPTS = 5
WINDOW_SEC = 600


def client_ip(request):
    return (
        request.META.get(
            "HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "0.0.0.0")
        )
        .split(",")[0]
        .strip()
    )


class LoginRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.endswith("/writer/login/") and request.method == "POST":
            ip = client_ip(request)
            user = request.POST.get("username", "").lower().strip() or "-"
            key = f"login:{ip}:{user}"
            data = cache.get(key, {"n": 0, "ts": time()})
            if data["n"] >= MAX_ATTEMPTS:
                return render(
                    request,
                    "writer/login.html",
                    {"form": None, "rate_limited": True},
                    status=429,
                )
            resp = self.get_response(request)
            if resp.status_code == 200:
                # view non ha redirect → probabile fallimento
                data["n"] += 1
                cache.set(key, data, WINDOW_SEC)
            else:
                cache.delete(key)  # su successo reset
            return resp
        return self.get_response(request)

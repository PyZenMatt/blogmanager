import logging
import os
import traceback

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("django.request")


class VerboseExceptionLoggingMiddleware(MiddlewareMixin):
    """
    In production (DEBUG=False) captures any exception, logs full traceback
    and request context (user, path, method, GET/POST sample) and re-raises.
    Active only if ENABLE_VERBOSE_ERRORS=true in env.
    """

    def process_exception(self, request, exception):
        if os.getenv("ENABLE_VERBOSE_ERRORS", "").lower() not in {"1", "true", "yes"}:
            return None
        user = getattr(request, "user", None)
        user_repr = f"{getattr(user, 'username', 'anon')} (id={getattr(user, 'pk', '?')})" if user else "anon"
        try:
            get_params = dict(request.GET.items()) if request.GET else {}
            post_params = dict(list(request.POST.items())[:20]) if request.POST else {}
        except Exception:
            get_params, post_params = {}, {}
        logger.error(
            "EXC in %s %s | user=%s | exc=%s\nGET=%s\nPOST(sample)=%s\nTRACEBACK:\n%s",
            request.method,
            request.path,
            user_repr,
            repr(exception),
            get_params,
            post_params,
            "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
        )
        # Return None to continue normal exception handling (and surface a 500)
        return None

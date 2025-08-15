import json
import logging
import uuid
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class ApiErrorAsJsonMiddleware(MiddlewareMixin):
	"""
	Se un errore 5xx genera una pagina HTML e il path inizia con /api/,
	converti la risposta in JSON stabile per evitare 'Unexpected token <' sul frontend.
	"""
	def process_response(self, request, response):
		try:
			path = request.path or ""
			if path.startswith("/api/") and response.status_code >= 500:
				ctype = (response.get("Content-Type") or "").lower()
				if "application/json" not in ctype:
					rid = str(uuid.uuid4())
					logger.exception("API 5xx converted to JSON; request_id=%s path=%s status=%s",
									 rid, path, response.status_code)
					payload = {
						"detail": "Internal server error.",
						"status": response.status_code,
						"request_id": rid,
					}
					response.content = json.dumps(payload).encode("utf-8")
					response["Content-Type"] = "application/json"
		except Exception:  # non bloccare mai la risposta
			logger.exception("ApiErrorAsJsonMiddleware failed")
		return response
Crea core/middleware.py con il middleware ApiErrorAsJsonMiddleware per convertire errori HTML in JSON su /api/.

import json
import logging
import re

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from smtplib import SMTPException

from .models import ContactMessage

logger = logging.getLogger(__name__)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_recipients():
    """
    Priorità:
    1) settings.CONTACT_RECIPIENTS (lista di email)
    2) settings.ADMINS / settings.MANAGERS (tuple (name, email))
    """
    recipients = list(getattr(settings, "CONTACT_RECIPIENTS", []) or [])
    if not recipients and getattr(settings, "ADMINS", None):
        recipients = [addr for _, addr in settings.ADMINS]
    if not recipients and getattr(settings, "MANAGERS", None):
        recipients = [addr for _, addr in settings.MANAGERS]
    return recipients


@csrf_exempt
def contact_submit(request):
    if request.method != "POST":
        logger.info("Method not allowed", extra={"method": request.method})
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        logger.warning("Invalid JSON", extra={"body": request.body.decode(errors="ignore")})
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip()
    message = (payload.get("message") or "").strip()
    honeypot = payload.get("honeypot", "")

    if honeypot:
        logger.warning("Honeypot triggered", extra={"ip": request.META.get("REMOTE_ADDR")})
        return JsonResponse({"success": False, "error": "Spam detected"}, status=400)

    if not name or len(name) > 100:
        logger.info("Invalid name", extra={"name": name})
        return JsonResponse({"success": False, "error": "Invalid name"}, status=400)
    if not email or not EMAIL_REGEX.match(email):
        logger.info("Invalid email", extra={"email": email})
        return JsonResponse({"success": False, "error": "Invalid email"}, status=400)
    if not message or len(message) < 5:
        logger.info("Message too short", extra={"message": message})
        return JsonResponse({"success": False, "error": "Message too short"}, status=400)

    # Salva su DB
    try:
        obj = ContactMessage.objects.create(name=name, email=email, message=message)
        logger.info("Contact message saved", extra={"user_name": name, "user_email": email, "id": obj.id})
    except Exception:
        logger.exception("Failed to save contact message to DB")
        return JsonResponse({"success": False, "error": "Internal server error"}, status=500)

    # Invio email via backend configurato (MailerSend/Anymail in prod)
    recipients = _get_recipients()
    if not recipients:
        logger.error("No recipients configured (CONTACT_RECIPIENTS/ADMINS/MANAGERS empty)")
        return JsonResponse({"success": False, "error": "Email recipients not configured"}, status=500)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not from_email:
        logger.error("DEFAULT_FROM_EMAIL not configured")
        return JsonResponse({"success": False, "error": "From email not configured"}, status=500)

    subject = f"Nuovo messaggio dal sito — {name}"
    body = (
        f"Nome: {name}\n"
        f"Email: {email}\n"
        f"ID Messaggio: {obj.id}\n\n"
        f"Messaggio:\n{message}\n"
    )

    try:
        email_msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipients,
            reply_to=[email],
        )
        # Se Anymail è attivo, questi campi vengono inoltrati al provider:
        if hasattr(email_msg, "tags"):
            email_msg.tags = ["contact"]
        if hasattr(email_msg, "metadata"):
            email_msg.metadata = {"contact_id": str(obj.id)}

        email_msg.send(fail_silently=False)
        logger.info("Notifica email inviata", extra={"recipient_count": len(recipients), "message_id": obj.id})
    except SMTPException:
        logger.exception("SMTP error while sending email")
        return JsonResponse({"success": False, "error": "Email send failed"}, status=502)
    except Exception:
        logger.exception("Unexpected error while sending email")
        return JsonResponse({"success": False, "error": "Internal server error"}, status=500)

    return JsonResponse({"success": True, "id": obj.id}, status=200)

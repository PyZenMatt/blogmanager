

import json
import re
import logging
from django.core.mail import send_mail
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ContactMessage

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
logger = logging.getLogger(__name__)

@csrf_exempt
def contact_submit(request):
    if request.method != "POST":
        logger.info("Method not allowed", extra={"method": request.method})
        return JsonResponse(
            {"success": False, "error": "Only POST allowed"},
            status=405
        )
    try:
        data = json.loads(request.body)
    except Exception:
        logger.warning(
            "Invalid JSON",
            extra={"body": request.body.decode(errors='ignore')}
        )
        return JsonResponse(
            {"success": False, "error": "Invalid JSON"},
            status=400
        )


    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()
    honeypot = data.get("honeypot", "")

    if honeypot:
        logger.warning(
            "Honeypot triggered",
            extra={"ip": request.META.get('REMOTE_ADDR')}
        )
        return JsonResponse(
            {"success": False, "error": "Spam detected"},
            status=400
        )

    if not name or len(name) > 100:
        logger.info("Invalid name", extra={"name": name})
        return JsonResponse(
            {"success": False, "error": "Invalid name"},
            status=400
        )
    if not email or not EMAIL_REGEX.match(email):
        logger.info("Invalid email", extra={"email": email})
        return JsonResponse(
            {"success": False, "error": "Invalid email"},
            status=400
        )
    if not message or len(message) < 5:
        logger.info("Message too short", extra={"message": message})
        return JsonResponse(
            {"success": False, "error": "Message too short"},
            status=400
        )

    ContactMessage.objects.create(name=name, email=email, message=message)
    logger.info(
        "Contact message saved",
        extra={"user_name": name, "user_email": email}
    )

    # Invio email di notifica
    try:
        recipient = os.environ.get('DEFAULT_FROM_EMAIL')
        send_mail(
            subject=f"Nuovo messaggio da {name}",
            message=f"Nome: {name}\nEmail: {email}\nMessaggio:\n{message}",
            from_email=None,  # Usa DEFAULT_FROM_EMAIL
            recipient_list=[recipient] if recipient else [],
            fail_silently=True,
        )
        logger.info(
            "Notifica email inviata",
            extra={"user_email": email, "recipient": recipient}
        )
    except Exception as e:
        logger.error("Errore invio email", extra={"error": str(e)})

    return JsonResponse({"success": True})

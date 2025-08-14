from rest_framework.views import exception_handler
from django.db import IntegrityError
from django.db.utils import OperationalError, DataError
from rest_framework import status
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Mappa errori DB tipici (charset/collation, overflow campi) a 400,
    evitando 500 su input utente.
    """
    if isinstance(exc, (IntegrityError, OperationalError, DataError)):
        logger.warning("DB input error", extra={"view": str(context.get("view")), "exc": str(exc)})
        return Response({"detail": "Input non valido per il database."}, status=status.HTTP_400_BAD_REQUEST)
    return exception_handler(exc, context)
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

class Command(BaseCommand):
    help = 'Crea o mostra il token DRF per un utente.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help="Username dell'utente")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"Utente '{username}' non trovato.")
        token, created = Token.objects.get_or_create(user=user)
        self.stdout.write(self.style.SUCCESS(f"Token per '{username}': {token.key}"))

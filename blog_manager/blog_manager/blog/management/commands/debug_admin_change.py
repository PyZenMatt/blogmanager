from django.core.management.base import BaseCommand, CommandError
from django.contrib import admin
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.apps import apps

class Command(BaseCommand):
    help = "Esegue la change_view admin per un <app_label.ModelName> e <pk> e stampa eventuale traceback."

    def add_arguments(self, parser):
        parser.add_argument("model", help="Formato: app_label.ModelName (es: blog.Post)")
        parser.add_argument("pk", type=str, help="Primary Key dell'oggetto")
        parser.add_argument("--username", default=None, help="Superuser da impersonare")

    def handle(self, *args, **opts):
        model_label = opts["model"]
        pk = opts["pk"]
        try:
            app_label, model_name = model_label.split(".")
        except ValueError:
            raise CommandError("Usa il formato app_label.ModelName, es: blog.Post")
        Model = apps.get_model(app_label, model_name)
        if not Model:
            raise CommandError(f"Model non trovato: {model_label}")
        try:
            obj = Model.objects.get(pk=pk)
        except Model.DoesNotExist:
            raise CommandError(f"{model_label} pk={pk} non esiste")

        site = admin.site
        try:
            ma = site._registry[Model]
        except KeyError:
            raise CommandError(f"{model_label} non registrato in admin")

        rf = RequestFactory()
        request = rf.get(f"/admin/{app_label}/{model_name.lower()}/{pk}/change/")
        User = get_user_model()
        if opts["username"]:
            user = User.objects.get(username=opts["username"])
        else:
            # prendi un superuser qualsiasi
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                raise CommandError("Nessun superuser presente. Creane uno e riprova.")
        request.user = user

        self.stdout.write(self.style.NOTICE(f"Provo change_view per {model_label} pk={pk} come {user.username}"))
        response = ma.change_view(request, str(pk))
        self.stdout.write(self.style.SUCCESS(f"OK: status_code={getattr(response, 'status_code', 'n/a')}"))

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from Max_app.models import Venta

User = get_user_model()


class Command(BaseCommand):
    help = "Elimina las ventas y clientes de demostración (cliente1..cliente8). No toca los productos."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="No pedir confirmación.")

    @transaction.atomic
    def handle(self, *args, **opts):
        demo = User.objects.filter(username__regex=r"^cliente[1-8]$", is_staff=False)
        ventas = Venta.objects.filter(cliente__user__in=demo)
        self.stdout.write(f"Se eliminarán {ventas.count()} ventas y {demo.count()} usuarios de demostración.")
        if not opts["yes"] and input("¿Continuar? (s/n): ").strip().lower() != "s":
            self.stdout.write("Cancelado.")
            return
        ventas.delete()
        demo.delete()
        self.stdout.write(self.style.SUCCESS("Listo: datos de demostración eliminados."))
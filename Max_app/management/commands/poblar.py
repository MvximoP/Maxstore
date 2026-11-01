from django.core.management.base import BaseCommand
from django.db import transaction

from Max_app.models import Plataforma, Producto

JUEGOS = [
    ("Super Mario Bros. 3", "Nintendo NES", 1988, "R", 45000, "mario3.jpg"),
    ("The Legend of Zelda", "Nintendo NES", 1986, "R", 52000, "Zelda_NES.jpg"),
    ("Sonic the Hedgehog 2", "Sega Genesis", 1992, "R", 28000, "sonic2.jpg"),
    ("Streets of Rage 2", "Sega Genesis", 1992, "R", 35000, "StreetsofRage_2.jpg"),
    ("Super Metroid", "Super Nintendo", 1994, "R", 60000, "SuperMetroid.jpg"),
    ("Chrono Trigger", "Super Nintendo", 1995, "R", 85000, "ChronoTrigger.jpg"),
    ("Crash Bandicoot", "PlayStation 1", 1996, "R", 22000, "crash.jpg"),
    ("Final Fantasy VII", "PlayStation 1", 1997, "R", 30000, "FinalFantasy7.jpg"),
    ("God of War Ragnarök", "PlayStation 5", 2022, "N", 54990, "GOW5.jpg"),
    ("Spider-Man 2", "PlayStation 5", 2023, "N", 59990, "Spiderman2.jpg"),
    ("Zelda: Tears of the Kingdom", "Nintendo Switch", 2023, "N", 62990, "ZeldaTOTK.jpg"),
    ("Mario Kart 8 Deluxe", "Nintendo Switch", 2017, "N", 52990, "Mario8.jpg"),
    ("Halo Infinite", "Xbox Series X", 2021, "N", 39990, "HaloInfinite.jpg"),
    ("Forza Horizon 5", "Xbox Series X", 2021, "N", 44990, "Forza.jpg"),
    ("Donkey Kong Country", "Super Nintendo", 1994, "R", 38000, "DKcountry.jpg"),
    ("Pokémon Red", "Game Boy", 1996, "R", 42000, "PokemonRojo.jpg"),
    ("Metal Gear Solid", "PlayStation 1", 1998, "R", 32000, "metalgear.jpg"),
    ("Elden Ring", "PlayStation 5", 2022, "N", 49990, "eldenring.jpg"),
    ("Super Mario Bros. Wonder", "Nintendo Switch", 2023, "N", 54990, "MarioWonder.jpg"),
    ("Starfield", "Xbox Series X", 2023, "N", 44990, "starfield.jpg"),
]

STOCK_INICIAL = 10


class Command(BaseCommand):
    help = "Carga el catálogo inicial de juegos. Se puede ejecutar varias veces sin duplicar."

    @transaction.atomic
    def handle(self, *args, **opts):
        for nombre, plat, anio, cond, precio, imagen in JUEGOS:
            pl, _ = Plataforma.objects.get_or_create(nombre=plat)
            p, _ = Producto.objects.get_or_create(
                nombre=nombre, plataforma=pl, condicion=cond,
                defaults={"anio_lanzamiento": anio, "precio": precio,
                          "stock": STOCK_INICIAL, "imagen": imagen},
            )
            if p.imagen != imagen:
                p.imagen = imagen
                p.save(update_fields=["imagen"])

        self.stdout.write(self.style.SUCCESS("Catálogo de juegos cargado."))
import re
from datetime import date
from itertools import cycle

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

# Create your models here.

def validar_rut(valor):
    "Valida RUT con módulo 11."
    rut = re.sub(r"[.\-\s]", "", valor).upper()
    if not re.fullmatch(r"\d{7,8}[\dK]", rut):
        raise ValidationError("Rut inválido.")
    cuerpo, dv = rut[:-1], rut[-1]
    suma = sum(int(d) * f for d, f in zip(reversed(cuerpo), cycle(range(2, 8))))
    resto = 11 - suma % 11
    esperado = "K" if resto == 10 else "0" if resto == 11 else str(resto)
    if dv != esperado:
        raise ValidationError("El rut no es válido.")


class Plataforma(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    class Condicion(models.TextChoices):
        NUEVO = "N", "Nuevo"
        RETRO = "R", "Retro"

    nombre = models.CharField(max_length=120)
    plataforma = models.ForeignKey(Plataforma, on_delete=models.PROTECT, related_name="productos")
    condicion = models.CharField(max_length=1, choices=Condicion.choices, default=Condicion.NUEVO)
    anio_lanzamiento = models.PositiveSmallIntegerField("año de lanzamiento", validators=[MinValueValidator(1970)])
    precio = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text="Precio en CLP")
    stock = models.PositiveIntegerField(default=0)
    descripcion = models.TextField(blank=True)
    imagen = models.URLField(max_length=100, blank=True, default="")
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["nombre", "plataforma", "condicion"], name="producto_unico"),
        ]
        indexes = [models.Index(fields=["activo", "condicion"])]

    def clean(self):
        if self.anio_lanzamiento and self.anio_lanzamiento > date.today().year + 1:
            raise ValidationError({"anio_lanzamiento": "Año de lanzamiento no válido."})

    def __str__(self):
        return f"{self.nombre} ({self.plataforma})"


class Cliente(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cliente")
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True, validators=[validar_rut])
    telefono = models.CharField(max_length=20, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_username()


class Venta(models.Model):
    class Estado(models.TextChoices):
        PAGADA = "P", "Pagada"
        PENDIENTE = "E", "Pendiente"
        ANULADA = "A", "Anulada"

    class Metodo(models.TextChoices):
        EFECTIVO = "EF", "Efectivo"
        TARJETA = "TA", "Tarjeta"

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="ventas")
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    total = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=1, choices=Estado.choices, default=Estado.PAGADA)
    metodo_pago = models.CharField(max_length=2, choices=Metodo.choices, default=Metodo.EFECTIVO)
    tarjeta_ultimos4 = models.CharField(max_length=4, blank=True)

    

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"Venta #{self.pk} – {self.cliente}"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="detalles")
    cantidad = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.PositiveIntegerField()  # precio congelado al momento de la compra

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

class Deseo(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deseos")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="deseos")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]
        constraints = [models.UniqueConstraint(fields=["user", "producto"], name="deseo_unico")]

    def __str__(self):
        return f"{self.user}  {self.producto}"


class Resena(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resenas")
    calificacion = models.PositiveSmallIntegerField(choices=[(i, f"{i} ★") for i in range(1, 6)])
    comentario = models.TextField(max_length=500)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Reseña de {self.user} ({self.calificacion})"
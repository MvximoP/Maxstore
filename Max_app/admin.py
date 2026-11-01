from django.contrib import admin

from .models import Cliente, DetalleVenta, Plataforma, Producto, Venta


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "plataforma", "condicion", "precio", "stock", "activo")
    list_filter = ("condicion", "plataforma", "activo")
    search_fields = ("nombre",)
    list_select_related = ("plataforma",)


class DetalleInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "fecha", "total", "estado")
    list_filter = ("estado",)
    inlines = [DetalleInline]


admin.site.register([Plataforma, Cliente])
# Solo los superusuarios pueden entrar al panel de Django
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser
# Register your models here.

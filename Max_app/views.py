from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.cache import cache
from django.db import transaction
from django.db.models import Avg, Count, F, FloatField, IntegerField, Q, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import PagoForm, ProductoForm, RecuperarClaveForm, RegistroForm
from .models import Cliente, DetalleVenta, Plataforma, Producto, Venta


def login_con_mensaje(view):
    """Sin sesión: avisa y manda a iniciar sesión / crear cuenta."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Inicie sesión o cree una cuenta para continuar.")
            if request.method == "GET":
                destino = request.get_full_path()
            else:
                destino = request.POST.get("next", "")
                if not url_has_allowed_host_and_scheme(destino, {request.get_host()}):
                    destino = reverse("catalogo")
            return redirect(f"{reverse('login')}?{urlencode({'next': destino})}")
        return view(request, *args, **kwargs)
    return wrapper


solo_staff = user_passes_test(lambda u: u.is_staff, login_url="admin_login")


def inicio(request):
    return render(request, "Max_app/inicio.html")


def quienes_somos(request):
    return render(request, "Max_app/quienes_somos.html")


# ---------- CATÁLOGO ----------
class CatalogoView(ListView):
    template_name = "Max_app/catalogo.html"
    context_object_name = "productos"
    paginate_by = 12

    def get_queryset(self):
        qs = Producto.objects.filter(activo=True).select_related("plataforma")
        q = self.request.GET.get("q", "").strip()
        condicion = self.request.GET.get("condicion")
        plataforma = self.request.GET.get("plataforma", "")
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(plataforma__nombre__icontains=q))
        if condicion in Producto.Condicion.values:
            qs = qs.filter(condicion=condicion)
        if plataforma.isdigit():
            qs = qs.filter(plataforma_id=plataforma)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["filtros"] = params.urlencode()
        ctx["plataformas"] = Plataforma.objects.all()
        return ctx


class ProductoMixin(UserPassesTestMixin):
    model = Producto
    success_url = reverse_lazy("catalogo")
    login_url = reverse_lazy("admin_login")

    def test_func(self):
        return self.request.user.is_staff


class ProductoCrearView(ProductoMixin, SuccessMessageMixin, CreateView):
    form_class = ProductoForm
    template_name = "Max_app/form_generico.html"
    success_message = "Producto creado correctamente."
    extra_context = {"titulo": "Nuevo producto", "boton": "Guardar"}


class ProductoEditarView(ProductoMixin, SuccessMessageMixin, UpdateView):
    form_class = ProductoForm
    template_name = "Max_app/form_generico.html"
    success_message = "Producto actualizado."
    extra_context = {"titulo": "Editar producto", "boton": "Guardar cambios"}


class ProductoEliminarView(ProductoMixin, DeleteView):
    def form_valid(self, form):
        try:
            resp = super().form_valid(form)
            messages.success(self.request, "Producto eliminado.")
            return resp
        except ProtectedError:  # tiene ventas: se desactiva para no perder historial
            self.object.activo = False
            self.object.save(update_fields=["activo"])
            messages.warning(self.request, "El producto tiene ventas asociadas; fue desactivado en vez de borrado.")
            return HttpResponseRedirect(self.get_success_url())


class StockInsuficiente(Exception):
    pass


def _items_carrito(carrito):
    productos = Producto.objects.filter(pk__in=carrito.keys(), activo=True).select_related("plataforma")
    items, total = [], 0
    for p in productos:
        cantidad = carrito[str(p.pk)]
        subtotal = p.precio * cantidad
        total += subtotal
        items.append({"producto": p, "cantidad": cantidad, "subtotal": subtotal})
    return items, total


@login_con_mensaje
@require_POST
def carrito_agregar(request, pk):
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    carrito = request.session.get("carrito", {})
    cantidad = carrito.get(str(pk), 0) + 1
    if cantidad > producto.stock:
        messages.warning(request, f"No hay más stock de {producto.nombre}.")
    else:
        carrito[str(pk)] = cantidad
        request.session["carrito"] = carrito
        messages.success(request, f"{producto.nombre} agregado al carrito.")
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}):
        destino = "catalogo"
    return redirect(destino)


@login_con_mensaje
@require_POST
def carrito_quitar(request, pk):
    carrito = request.session.get("carrito", {})
    if carrito.pop(str(pk), None) is not None:
        request.session["carrito"] = carrito
    return redirect("carrito")


@login_con_mensaje
def carrito_ver(request):
    items, total = _items_carrito(request.session.get("carrito", {}))
    return render(request, "Max_app/carrito.html", {"items": items, "total": total})


@login_con_mensaje
@require_POST
def carrito_confirmar(request):
    "El botón 'confirmar' del carrito lleva a elegir método de pago."
    if not request.session.get("carrito"):
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("catalogo")
    return redirect("checkout")


def _registrar_venta(user, carrito, datos):
    """Crea Venta + DetalleVenta y descuenta stock, todo en una transacción (PostgreSQL)."""
    cliente, _ = Cliente.objects.get_or_create(user=user)
    es_tarjeta = datos["metodo"] == Venta.Metodo.TARJETA
    with transaction.atomic():
        productos = {
            str(p.pk): p
            for p in Producto.objects.select_for_update().filter(pk__in=carrito.keys(), activo=True)
        }
        lineas, total = [], 0
        for pk, cantidad in carrito.items():
            p = productos.get(pk)
            if p is None or p.stock < cantidad:
                raise StockInsuficiente(p.nombre if p else "producto no disponible")
            p.stock -= cantidad
            total += p.precio * cantidad
            lineas.append((p, cantidad))

        venta = Venta.objects.create(
            cliente=cliente,
            total=total,
            metodo_pago=datos["metodo"],
            estado=Venta.Estado.PAGADA if es_tarjeta else Venta.Estado.PENDIENTE,
            tarjeta_ultimos4=datos["numero"][-4:] if es_tarjeta else "",
        )
        DetalleVenta.objects.bulk_create(
            [DetalleVenta(venta=venta, producto=p, cantidad=c, precio_unitario=p.precio) for p, c in lineas]
        )
        Producto.objects.bulk_update([p for p, _ in lineas], ["stock"])
    return venta


@login_con_mensaje
def checkout(request):
    carrito = request.session.get("carrito", {})
    if not carrito:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("catalogo")

    form = PagoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            venta = _registrar_venta(request.user, carrito, form.cleaned_data)
        except StockInsuficiente as e:
            messages.error(request, f"Stock insuficiente: {e}.")
            return redirect("carrito")
        request.session.pop("carrito", None)
        if venta.estado == Venta.Estado.PAGADA:
            messages.success(request, f"Pago con tarjeta aprobado. Compra #{venta.pk} registrada.")
        else:
            messages.success(request, f"Compra #{venta.pk} registrada. Pagas en efectivo al retirar.")
        return redirect("mis_compras")

    items, total = _items_carrito(carrito)
    return render(request, "Max_app/checkout.html", {"form": form, "items": items, "total": total})


@login_con_mensaje
def mis_compras(request):
    ventas = Venta.objects.filter(cliente__user=request.user).prefetch_related("detalles__producto")
    return render(request, "Max_app/mis_compras.html", {"ventas": ventas})


# ---------- REGISTRO ----------
def registro(request):
    if request.user.is_authenticated:
        return redirect("catalogo")
    form = RegistroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        messages.success(request, "¡Cuenta creada! Bienvenido a MaxStore.")
        return redirect("catalogo")
    return render(request, "Max_app/form_generico.html",
                  {"form": form, "titulo": "Crear cuenta", "boton": "Registrarme"})


# ---------- RECUPERAR CONTRASEÑA (usuario + teléfono) ----------
def recuperar_clave(request):
    if request.user.is_authenticated:
        return redirect("configuracion")

    form = RecuperarClaveForm(request.POST or None)
    if request.method == "POST":
        usuario = (request.POST.get("username") or "").strip().lower()
        clave_cache = f"recuperar:{usuario}"
        intentos = cache.get(clave_cache, 0)

        if intentos >= 5:
            messages.error(request, "Demasiados intentos. Espera 15 minutos e inténtalo de nuevo.")
        elif form.is_valid():
            user = form.user
            user.set_password(form.cleaned_data["password1"])
            user.save(update_fields=["password"])
            cache.delete(clave_cache)
            messages.success(request, "Contraseña actualizada. Ya puedes iniciar sesión.")
            return redirect("login")
        elif form.non_field_errors():  # los datos no coincidieron: cuenta como intento fallido
            cache.set(clave_cache, intentos + 1, 15 * 60)

    return render(request, "Max_app/form_generico.html", {
        "form": form, "titulo": "Recuperar contraseña", "boton": "Cambiar contraseña",
    })


# ---------- DASHBOARD (solo personal) ----------
@solo_staff
def dashboard(request):
    pagadas = Venta.objects.filter(estado=Venta.Estado.PAGADA)
    lineas = DetalleVenta.objects.filter(venta__estado=Venta.Estado.PAGADA)
    ingreso = Sum(F("cantidad") * F("precio_unitario"), output_field=IntegerField())

    resumen = pagadas.aggregate(
        ingresos=Coalesce(Sum("total"), 0, output_field=IntegerField()),
        ventas=Count("id"),
        ticket=Coalesce(Avg("total"), 0.0, output_field=FloatField()),
    )
    inventario = Producto.objects.filter(activo=True).aggregate(
        unidades=Coalesce(Sum("stock"), 0, output_field=IntegerField()),
        valor=Coalesce(Sum(F("precio") * F("stock"), output_field=IntegerField()), 0, output_field=IntegerField()),
    )

    por_mes = list(
        pagadas.annotate(mes=TruncMonth("fecha")).values("mes")
        .annotate(total=Sum("total")).order_by("-mes")[:12]
    )[::-1]

    por_condicion = list(
        lineas.values("producto__condicion").annotate(ingresos=ingreso).order_by("-ingresos")
    )
    nombres_cond = dict(Producto.Condicion.choices)
    for fila in por_condicion:
        fila["etiqueta"] = nombres_cond.get(fila["producto__condicion"], "—")

    grafico = {
        "meses": [m["mes"].strftime("%m/%Y") for m in por_mes],
        "ingresos_mes": [m["total"] for m in por_mes],
        "cond_labels": [f["etiqueta"] for f in por_condicion],
        "cond_valores": [f["ingresos"] for f in por_condicion],
    }

    ctx = {
        "resumen": resumen,
        "inventario": inventario,
        "clientes": Cliente.objects.count(),
        "top_productos": lineas.values("producto__nombre", "producto__plataforma__nombre")
                               .annotate(unidades=Sum("cantidad"), ingresos=ingreso).order_by("-unidades")[:5],
        "por_plataforma": lineas.values("producto__plataforma__nombre")
                                .annotate(ingresos=ingreso).order_by("-ingresos")[:6],
        "mejores_clientes": pagadas.values("cliente__user__username")
                                   .annotate(total=Sum("total"), compras=Count("id")).order_by("-total")[:5],
        "stock_bajo": Producto.objects.filter(activo=True, stock__lte=3)
                              .select_related("plataforma").order_by("stock")[:8],
        "grafico": grafico,
        "pendientes": Venta.objects.filter(estado=Venta.Estado.PENDIENTE)
                           .select_related("cliente__user").order_by("-fecha")[:10],
        "total_pendientes": Venta.objects.filter(estado=Venta.Estado.PENDIENTE).count(),
    }
    return render(request, "Max_app/dashboard.html", ctx)


@solo_staff
@require_POST
def venta_marcar_pagada(request, pk):
    """El administrador confirma el pago en efectivo: la venta pasa a Pagada y entra al dashboard."""
    n = Venta.objects.filter(pk=pk, estado=Venta.Estado.PENDIENTE).update(estado=Venta.Estado.PAGADA)
    if n:
        messages.success(request, f"Venta #{pk} marcada como pagada.")
    return redirect("dashboard")
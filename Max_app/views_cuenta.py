from django.contrib import messages
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CambiarClaveForm, PerfilForm, ResenaForm
from .models import Deseo, Producto, Resena
from .views import login_con_mensaje


# ---------- CONFIGURACIÓN DE LA CUENTA ----------
@login_con_mensaje
def configuracion(request):
    form = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tus datos se actualizaron.")
        return redirect("configuracion")
    return render(request, "Max_app/configuracion.html",
                  {"form": form, "total_deseos": request.user.deseos.count()})


class CambiarClaveView(SuccessMessageMixin, PasswordChangeView):
    form_class = CambiarClaveForm
    template_name = "Max_app/form_generico.html"
    success_url = reverse_lazy("configuracion")
    success_message = "Tu contraseña fue cambiada."
    extra_context = {"titulo": "Cambiar contraseña", "boton": "Guardar contraseña"}


# ---------- LISTA DE DESEOS ----------
@login_con_mensaje
def lista_deseos(request):
    deseos = request.user.deseos.select_related("producto__plataforma")
    return render(request, "Max_app/lista_deseos.html", {"deseos": deseos})


@login_con_mensaje
@require_POST
def deseo_alternar(request, pk):
    """Agrega el juego a la lista de deseos, o lo quita si ya estaba."""
    producto = get_object_or_404(Producto, pk=pk, activo=True)
    deseo, creado = Deseo.objects.get_or_create(user=request.user, producto=producto)
    if creado:
        messages.success(request, f"{producto.nombre} se agregó a tu lista de deseos.")
    else:
        deseo.delete()
        messages.info(request, f"{producto.nombre} se quitó de tu lista de deseos.")
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, {request.get_host()}):
        destino = "catalogo"
    return redirect(destino)


# ---------- RESEÑAS ----------
def resenas(request):
    form = None
    if request.user.is_authenticated:
        form = ResenaForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            r = form.save(commit=False)
            r.user = request.user
            r.save()
            messages.success(request, "¡Gracias por tu reseña!")
            return redirect("resenas")
    return render(request, "Max_app/resenas.html", {
        "form": form,
        "resenas": Resena.objects.select_related("user")[:50],
        "resumen": Resena.objects.aggregate(promedio=Avg("calificacion"), total=Count("id")),
    })
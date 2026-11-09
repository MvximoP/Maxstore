from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_cuenta
from .forms import AdminLoginForm, LoginForm

urlpatterns = [

    # --- Tienda / Público ---
    path("", views.inicio, name="inicio"),
    path("catalogo/", views.CatalogoView.as_view(), name="catalogo"),
    path("quienes-somos/", views.quienes_somos, name="quienes_somos"),

    # --- Gestión de productos (admin) ---
    path("producto/nuevo/", views.ProductoCrearView.as_view(), name="producto_crear"),
    path("producto/<int:pk>/editar/", views.ProductoEditarView.as_view(), name="producto_editar"),
    path("producto/<int:pk>/eliminar/", views.ProductoEliminarView.as_view(), name="producto_eliminar"),

    # --- Carrito y compras ---
    path("carrito/", views.carrito_ver, name="carrito"),
    path("carrito/agregar/<int:pk>/", views.carrito_agregar, name="carrito_agregar"),
    path("carrito/quitar/<int:pk>/", views.carrito_quitar, name="carrito_quitar"),
    path("carrito/confirmar/", views.carrito_confirmar, name="carrito_confirmar"),
    path("pago/", views.checkout, name="checkout"),
    path("mis-compras/", views.mis_compras, name="mis_compras"),

    # --- Dashboard / ventas (admin) ---
    path("dashboard/", views.dashboard, name="dashboard"),
    path("venta/<int:pk>/pagar/", views.venta_marcar_pagada, name="venta_pagar"),

    # --- Cuenta del usuario ---
    path("configuracion/", views_cuenta.configuracion, name="configuracion"),
    path("configuracion/clave/", views_cuenta.CambiarClaveView.as_view(), name="cambiar_clave"),
    path("lista-deseos/", views_cuenta.lista_deseos, name="lista_deseos"),
    path("deseos/<int:pk>/", views_cuenta.deseo_alternar, name="deseo_alternar"),
    path("resenas/", views_cuenta.resenas, name="resenas"),

    # --- Registro / Autenticación ---
    path("registro/", views.registro, name="registro"),
    path("recuperar-clave/", views.recuperar_clave, name="recuperar_clave"),
    path("ingresar/", auth_views.LoginView.as_view(
        template_name="Max_app/form_generico.html",
        authentication_form=LoginForm,
        redirect_authenticated_user=True,
        extra_context={"titulo": "Ingresar", "boton": "Ingresar"},
    ), name="login"),
    path("admin-acceso/", auth_views.LoginView.as_view(
        template_name="Max_app/form_generico.html",
        authentication_form=AdminLoginForm,
        next_page="dashboard",
        extra_context={"titulo": "Acceso administrador", "boton": "Entrar como administrador"},
    ), name="admin_login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
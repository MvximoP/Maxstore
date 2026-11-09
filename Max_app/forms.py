import re
from datetime import date

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.db import transaction

from .models import Cliente, Producto, Venta, Resena, validar_rut

User = get_user_model()

class BootstrapMixin:
    "Aplica clases Bootstrap a todos los campos."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, forms.CheckboxInput):
                clase = "form-check-input"
            elif isinstance(w, forms.Select):
                clase = "form-select"
            else:
                clase = "form-control"
            w.attrs["class"] = clase


class LoginForm(BootstrapMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nombre de usuario"
        self.fields["password"].label = "Contraseña"


class AdminLoginForm(LoginForm):
    "Login exclusivo para administradores."
    
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Usuario o contraseña incorrectos.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
       
        if not (user.is_staff or user.is_superuser):
            raise forms.ValidationError(
                "Esta cuenta no tiene permisos de administrador.",
                code="no_admin",
            )


class RegistroForm(BootstrapMixin, UserCreationForm):
    email = forms.EmailField(required=True)
    rut = forms.CharField(max_length=12, validators=[validar_rut], help_text="Ej: 12.345.678-5")
    telefono = forms.CharField(max_length=20, help_text="Ej: +56 9 1234 5678")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nombre de usuario"
        self.fields["username"].help_text = "Mínimo 8 caracteres. Solo letras, números y @/./+/-/_"
        self.fields["email"].label = "Correo electrónico"
        self.fields["rut"].label = "RUT"
        self.fields["telefono"].label = "Teléfono"
        self.fields["password1"].label = "Contraseña"
        self.fields["password1"].help_text = (
            "Mínimo 10 caracteres. No puede ser solo números ni una contraseña demasiado común."
        )
        self.fields["password2"].label = "Repetir contraseña"
        self.fields["password2"].help_text = "Escriba la misma contraseña para confirmar."

    def clean_username(self):
        usuario = self.cleaned_data["username"].strip()
        if len(usuario) < 8:
            raise forms.ValidationError("El nombre de usuario debe tener al menos 8 caracteres.")
        return usuario

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if "@" not in email:
            raise forms.ValidationError("El correo debe contener un @.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    def clean_rut(self):
        rut = re.sub(r"[.\-\s]", "", self.cleaned_data["rut"]).upper()
        rut = f"{rut[:-1]}-{rut[-1]}"
        if Cliente.objects.filter(rut=rut).exists():
            raise forms.ValidationError("Este RUT ya está registrado.")
        return rut

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        if len(re.sub(r"\D", "", telefono)) < 8:
            raise forms.ValidationError("Ingresa un teléfono válido (mínimo 8 dígitos).")
        return telefono

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()
        Cliente.objects.create(
            user=user,
            rut=self.cleaned_data["rut"],
            telefono=self.cleaned_data["telefono"],
        )
        return user


class PerfilForm(BootstrapMixin, forms.ModelForm):
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono")

    class Meta:
        model = User
        fields = ("username", "email")
        labels = {"username": "Nombre de usuario", "email": "Correo electrónico"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        cliente = getattr(self.instance, "cliente", None)
        if cliente:
            self.fields["telefono"].initial = cliente.telefono

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        cliente, _ = Cliente.objects.get_or_create(user=user)
        cliente.telefono = self.cleaned_data["telefono"]
        cliente.save(update_fields=["telefono"])
        return user


class CambiarClaveForm(BootstrapMixin, PasswordChangeForm):
    pass



class ProductoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "plataforma", "condicion", "anio_lanzamiento", "precio", "stock", "imagen", "activo"]

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()


class ResenaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Resena
        fields = ["calificacion", "comentario"]
        labels = {"calificacion": "Calificación", "comentario": "Tu opinión"}
        widgets = {"comentario": forms.Textarea(attrs={"rows": 3})}


def _luhn_valido(numero):
    total = 0
    for i, d in enumerate(map(int, reversed(numero))):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class PagoForm(forms.Form):
    metodo = forms.ChoiceField(
        label="Método de pago", choices=Venta.Metodo.choices,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial=Venta.Metodo.EFECTIVO,
    )
    titular = forms.CharField(label="Nombre del titular", required=False, max_length=60)
    numero = forms.CharField(label="Número de tarjeta", required=False, max_length=23)
    vencimiento = forms.CharField(label="Vencimiento (MM/AA)", required=False, max_length=5)
    cvv = forms.CharField(label="CVV", required=False, max_length=4,
                          widget=forms.PasswordInput(render_value=False))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if nombre != "metodo":
                campo.widget.attrs["class"] = "form-control"
        self.fields["numero"].widget.attrs["placeholder"] = "1234 5678 9012 3456"
        self.fields["vencimiento"].widget.attrs["placeholder"] = "MM/AA"
        self.fields["cvv"].widget.attrs["autocomplete"] = "off"

    def clean(self):
        data = super().clean()
        if data.get("metodo") != Venta.Metodo.TARJETA:
            return data

        if len((data.get("titular") or "").strip()) < 3:
            self.add_error("titular", "Ingrese el nombre del titular.")

        numero = re.sub(r"[\s-]", "", data.get("numero") or "")
        if not (numero.isdigit() and 13 <= len(numero) <= 19 and _luhn_valido(numero)):
            self.add_error("numero", "Número de tarjeta inválido.")
        data["numero"] = numero

        m = re.fullmatch(r"(0[1-9]|1[0-2])/(\d{2})", (data.get("vencimiento") or "").strip())
        if not m:
            self.add_error("vencimiento", "Use el formato MM/AA.")
        else:
            hoy = date.today()
            if (2000 + int(m.group(2)), int(m.group(1))) < (hoy.year, hoy.month):
                self.add_error("vencimiento", "La tarjeta está vencida.")

        if not re.fullmatch(r"\d{3,4}", data.get("cvv") or ""):
            self.add_error("cvv", "El CVV debe tener 3 o 4 dígitos.")
        return data


# ---------- RECUPERAR CONTRASEÑA (usuario + teléfono) ----------
def _solo_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def _mismo_telefono(a, b):
    """Compara teléfonos ignorando espacios, guiones, paréntesis y el +56."""
    a, b = _solo_digitos(a), _solo_digitos(b)
    return len(a) >= 8 and len(b) >= 8 and a[-9:] == b[-9:]


class RecuperarClaveForm(BootstrapMixin, forms.Form):
    """Restablece la contraseña de un usuario normal verificando usuario + teléfono."""
    username = forms.CharField(label="Nombre de usuario", max_length=150)
    telefono = forms.CharField(label="Teléfono", max_length=20,
                               help_text="El teléfono con el que te registraste. Ej: +56 9 1234 5678")
    password1 = forms.CharField(
        label="Contraseña nueva", strip=False, widget=forms.PasswordInput,
        help_text="Mínimo 10 caracteres. No puede ser solo números ni una contraseña demasiado común.",
    )
    password2 = forms.CharField(label="Repetir contraseña nueva", strip=False, widget=forms.PasswordInput)

    user = None

    def clean(self):
        data = super().clean()
        username = (data.get("username") or "").strip()
        telefono = data.get("telefono") or ""
        p1, p2 = data.get("password1"), data.get("password2")

        # 1) Reglas de la contraseña (no dependen del usuario)
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    password_validation.validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        if self.errors:
            return data

        # 2) Identidad: solo usuarios normales (nunca staff ni superusuarios)
        user = (User.objects
                .filter(username__iexact=username, is_staff=False, is_superuser=False, is_active=True)
                .first())
        cliente = getattr(user, "cliente", None) if user else None
        if not cliente or not _mismo_telefono(cliente.telefono, telefono):
            raise forms.ValidationError("Los datos no coinciden con ningún usuario.")
        self.user = user
        return data
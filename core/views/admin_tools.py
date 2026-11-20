"""Администрирование пользователей и производственных справочников (UC-17, UC-18)."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import ActionLog, AppUser, Material, ProductType, Role, RoleCode


def _admin_only(request):
    return request.user.is_authenticated and request.user.role.code == RoleCode.ADMIN


class AdminStyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")


class UserForm(forms.ModelForm):
    temporary_password = forms.CharField(
        label="Временный пароль", required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Не менее 8 символов, должны быть буквы и цифры. После входа пользователь сменит пароль.",
    )

    class Meta:
        model = AppUser
        fields = ("login", "full_name", "role", "is_blocked")
        labels = {"login": "Логин", "full_name": "ФИО", "role": "Роль", "is_blocked": "Заблокировать вход"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.order_by("id")
        self.fields["role"].empty_label = "Выберите роль"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")
        if self.instance.pk:
            self.fields["temporary_password"].help_text = "Оставьте пустым, если сбрасывать пароль не нужно. Новый пароль потребуется сменить при следующем входе."

    def clean_temporary_password(self):
        value = self.cleaned_data.get("temporary_password", "")
        if value and (len(value) < 8 or not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value)):
            raise forms.ValidationError("Пароль должен содержать не менее 8 символов, буквы и цифры.")
        return value


class ProductTypeForm(AdminStyledForm):
    class Meta:
        model = ProductType
        fields = ("name",)
        labels = {"name": "Наименование вида продукции"}


class MaterialForm(AdminStyledForm):
    class Meta:
        model = Material
        fields = ("name", "kind", "grammage", "is_active")
        labels = {"name": "Наименование", "kind": "Тип материала", "grammage": "Плотность, г/м²", "is_active": "Доступен для выбора"}
        widgets = {"grammage": forms.NumberInput(attrs={"min": 1})}

    def clean_grammage(self):
        value = self.cleaned_data.get("grammage")
        if value is not None and value <= 0:
            raise forms.ValidationError("Плотность должна быть положительным числом.")
        return value


@login_required
def user_list(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Управлять пользователями может только администратор.")
    return render(request, "core/user_list.html", {"users": AppUser.objects.select_related("role").order_by("full_name", "login")})


@login_required
def user_create(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Создавать пользователей может только администратор.")
    form = UserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        password = data["temporary_password"]
        if not password:
            form.add_error("temporary_password", "Для новой учётной записи укажите временный пароль.")
        else:
            user = AppUser.objects.create_user(
                login=data["login"], password=password, full_name=data["full_name"],
                role=data["role"], is_blocked=data["is_blocked"],
            )
            user.password_changed_at = None
            user.save(update_fields=["password_changed_at"])
            ActionLog.objects.create(user=request.user, action="user_create", details=f"Создан пользователь {user.login}, роль: {user.role.name}")
            messages.success(request, f"Пользователь «{user.login}» создан. При первом входе он должен сменить временный пароль.")
            return redirect("user_list")
    return render(request, "core/admin_form.html", {"form": form, "page_title": "Новый пользователь", "back_url": "user_list"})


@login_required
def user_edit(request, pk):
    if not _admin_only(request):
        return HttpResponseForbidden("Изменять пользователей может только администратор.")
    target = get_object_or_404(AppUser.objects.select_related("role"), pk=pk)
    form = UserForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if target.pk == request.user.pk and data["is_blocked"]:
            form.add_error("is_blocked", "Нельзя заблокировать собственную учётную запись.")
        elif target.pk == request.user.pk and data["role"].code != RoleCode.ADMIN:
            form.add_error("role", "Нельзя снять роль администратора с текущей учётной записи.")
        else:
            user = form.save(commit=False)
            user.save()
            if data["temporary_password"]:
                user.set_password(data["temporary_password"])
                user.password_changed_at = None
                user.save(update_fields=["password", "password_changed_at"])
            ActionLog.objects.create(user=request.user, action="user_edit", details=f"Изменён пользователь {user.login}; сброс пароля: {'да' if data['temporary_password'] else 'нет'}")
            messages.success(request, f"Учётная запись «{user.login}» обновлена.")
            return redirect("user_list")
    return render(request, "core/admin_form.html", {"form": form, "page_title": f"Изменить пользователя: {target.login}", "back_url": "user_list", "target": target})


@login_required
def reference_list(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Вести справочники может только администратор.")
    return render(request, "core/reference_list.html", {
        "product_types": ProductType.objects.order_by("name"),
        "materials": Material.objects.order_by("name"),
    })


@login_required
def product_type_create(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Вести справочники может только администратор.")
    form = ProductTypeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        ActionLog.objects.create(user=request.user, action="reference_create", details=f"Добавлен вид продукции: {obj.name}")
        messages.success(request, "Вид продукции добавлен.")
        return redirect("reference_list")
    return render(request, "core/admin_form.html", {"form": form, "page_title": "Новый вид продукции", "back_url": "reference_list"})


@login_required
def product_type_edit(request, pk):
    if not _admin_only(request):
        return HttpResponseForbidden("Вести справочники может только администратор.")
    obj = get_object_or_404(ProductType, pk=pk)
    form = ProductTypeForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        ActionLog.objects.create(user=request.user, action="reference_edit", details=f"Изменён вид продукции: {obj.name}")
        messages.success(request, "Вид продукции обновлён.")
        return redirect("reference_list")
    return render(request, "core/admin_form.html", {"form": form, "page_title": "Изменить вид продукции", "back_url": "reference_list"})


@login_required
def material_create(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Вести справочники может только администратор.")
    form = MaterialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        ActionLog.objects.create(user=request.user, action="reference_create", details=f"Добавлен материал: {obj.name}")
        messages.success(request, "Материал добавлен.")
        return redirect("reference_list")
    return render(request, "core/admin_form.html", {"form": form, "page_title": "Новый материал", "back_url": "reference_list"})


@login_required
def material_edit(request, pk):
    if not _admin_only(request):
        return HttpResponseForbidden("Вести справочники может только администратор.")
    obj = get_object_or_404(Material, pk=pk)
    form = MaterialForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        ActionLog.objects.create(user=request.user, action="reference_edit", details=f"Изменён материал: {obj.name}")
        messages.success(request, "Материал обновлён.")
        return redirect("reference_list")
    return render(request, "core/admin_form.html", {"form": form, "page_title": "Изменить материал", "back_url": "reference_list"})

"""Формы входа, смены пароля и фильтра заказов."""
from django import forms

from core.models import OrderStatus


class StyledForm(forms.Form):
    """Добавляет всем полям общий CSS-класс."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")


class LoginForm(StyledForm):
    login = forms.CharField(
        label="Логин", max_length=50,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Пароль", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class PasswordChangeForm(StyledForm):
    current_password = forms.CharField(
        label="Текущий пароль *", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label="Новый пароль *", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    repeat_password = forms.CharField(
        label="Повторите новый пароль *", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        value = self.cleaned_data["current_password"]
        if not self.user.check_password(value):
            raise forms.ValidationError("Текущий пароль указан неверно.")
        return value

    def clean_new_password(self):
        value = self.cleaned_data["new_password"]
        # ЗИ-02: не менее 8 символов, буквы и цифры
        if len(value) < 8:
            raise forms.ValidationError("Пароль должен содержать не менее 8 символов.")
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise forms.ValidationError("Пароль должен содержать буквы и цифры.")
        return value

    def clean(self):
        cleaned = super().clean()
        new = cleaned.get("new_password")
        if new:
            if new == cleaned.get("current_password"):
                self.add_error("new_password", "Новый пароль должен отличаться от текущего.")
            if cleaned.get("repeat_password") and new != cleaned["repeat_password"]:
                self.add_error("repeat_password", "Пароли не совпадают.")
        return cleaned


class OrderFilterForm(StyledForm):
    number = forms.CharField(label="Номер", required=False, max_length=20)
    client = forms.CharField(label="Клиент", required=False, max_length=200)
    product = forms.CharField(label="Продукция", required=False, max_length=100)
    status = forms.ModelChoiceField(
        label="Статус", required=False, queryset=OrderStatus.objects.all(),
        empty_label="Все",
    )
    due = forms.DateField(
        label="Срок готовности до", required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    executor = forms.CharField(label="Исполнитель", required=False, max_length=150)

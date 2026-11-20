"""Вход, выход и смена пароля (ФТ-01, ФТ-02)."""
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.forms import LoginForm, PasswordChangeForm
from core.services.login_guard import is_locked, write_log

# Одно и то же сообщение для неверного логина и неверного пароля (ФТ-01)
BAD_CREDENTIALS = "Неверный логин или пароль."
LOCKED = "Вход временно заблокирован из-за неудачных попыток. Повторите через 15 минут."


def login_view(request):
    if request.user.is_authenticated:
        return redirect("orders")

    form = LoginForm(request.POST or None)
    error = None
    if request.method == "POST":
        if not form.is_valid():
            error = "Введите логин и пароль."
        else:
            name = form.cleaned_data["login"]
            if is_locked(name):
                write_log(None, "login_blocked", name)
                error = LOCKED
            else:
                user = authenticate(request, login=name, password=form.cleaned_data["password"])
                if user is None:
                    write_log(None, "login_failed", name)
                    error = BAD_CREDENTIALS
                else:
                    login(request, user)
                    write_log(user, "login_ok", name)
                    target = request.GET.get("next", "")
                    if target and url_has_allowed_host_and_scheme(target, allowed_hosts=None):
                        return redirect(target)
                    return redirect("orders")
    return render(request, "core/login.html", {"form": form, "error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def password_change(request):
    user = request.user
    forced = user.password_changed_at is None
    form = PasswordChangeForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password"])  # хеш Argon2id с солью
        user.password_changed_at = timezone.now()
        user.save()
        update_session_auth_hash(request, user)
        write_log(user, "password_change")
        return redirect("orders")
    return render(request, "core/password_change.html", {"form": form, "forced": forced})

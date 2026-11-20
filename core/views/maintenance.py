"""Резервное копирование, восстановление и просмотр журнала (UC-19—UC-21)."""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import ActionLog, AppUser, Order, RoleCode


def _admin_only(request):
    return request.user.is_authenticated and request.user.role.code == RoleCode.ADMIN


def _backup_dir():
    path = Path(settings.BASE_DIR) / "backups"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _pg_env():
    cfg = settings.DATABASES["default"]
    env = os.environ.copy()
    env["PGPASSWORD"] = str(cfg.get("PASSWORD", ""))
    return cfg, env


def _pg_command(binary):
    configured = os.getenv("PG_DUMP_PATH" if binary == "pg_dump" else "PG_RESTORE_PATH")
    found = configured or shutil.which(binary)
    if not found:
        raise RuntimeError(f"Не найдена программа {binary}. Установите PostgreSQL client tools или задайте путь в переменной окружения.")
    return found


def _db_args(cfg):
    return ["--host", str(cfg.get("HOST") or "localhost"), "--port", str(cfg.get("PORT") or "5432"), "--username", str(cfg["USER"]), "--dbname", str(cfg["NAME"])]


@login_required
def backup_list(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Резервное копирование доступно только администратору.")
    files = []
    for path in sorted(_backup_dir().glob("printuchet_*.dump"), key=lambda p: p.stat().st_mtime, reverse=True):
        files.append({"name": path.name, "size": path.stat().st_size, "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.get_current_timezone())})
    return render(request, "core/maintenance.html", {"backups": files})


@login_required
def backup_create(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Создавать резервные копии может только администратор.")
    if request.method != "POST":
        return redirect("backup_list")
    cfg, env = _pg_env()
    filename = f"printuchet_{timezone.now():%Y%m%d_%H%M%S}.dump"
    destination = _backup_dir() / filename
    try:
        result = subprocess.run([_pg_command("pg_dump"), *_db_args(cfg), "--format=custom", "--no-owner", "--file", str(destination)], env=env, capture_output=True, text=True, timeout=600, check=False)
        if result.returncode:
            destination.unlink(missing_ok=True)
            raise RuntimeError(result.stderr.strip() or "pg_dump завершился с ошибкой")
        size = destination.stat().st_size
        ActionLog.objects.create(user=request.user, action="backup_create", details=f"Файл: {filename}; размер: {size} байт")
        messages.success(request, f"Резервная копия создана: {filename} ({size:,} байт).")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        ActionLog.objects.create(user=request.user, action="backup_error", details=str(exc)[:500])
        messages.error(request, f"Не удалось создать копию: {exc}")
    return redirect("backup_list")


@login_required
def backup_restore(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Восстанавливать базу может только администратор.")
    if request.method != "POST" or not request.POST.get("filename") or request.POST.get("confirm") != "yes":
        messages.error(request, "Для восстановления выберите копию и подтвердите операцию.")
        return redirect("backup_list")
    filename = Path(request.POST["filename"]).name
    source = _backup_dir() / filename
    if not filename.startswith("printuchet_") or source.suffix != ".dump" or not source.is_file():
        messages.error(request, "Выбранный файл резервной копии не найден.")
        return redirect("backup_list")
    cfg, env = _pg_env()
    stamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    safety_file = _backup_dir() / f"printuchet_before_restore_{stamp}.dump"
    try:
        dump = subprocess.run([_pg_command("pg_dump"), *_db_args(cfg), "--format=custom", "--no-owner", "--file", str(safety_file)], env=env, capture_output=True, text=True, timeout=600, check=False)
        if dump.returncode:
            raise RuntimeError("Не удалось создать страховочную копию перед восстановлением: " + (dump.stderr.strip() or "ошибка pg_dump"))
        restore = subprocess.run([_pg_command("pg_restore"), *_db_args(cfg), "--clean", "--if-exists", "--no-owner", "--exit-on-error", str(source)], env=env, capture_output=True, text=True, timeout=1200, check=False)
        if restore.returncode:
            raise RuntimeError("Восстановление завершилось с ошибкой: " + (restore.stderr.strip() or "ошибка pg_restore") + f" Страховочная копия: {safety_file.name}")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        ActionLog.objects.create(user=request.user, action="backup_restore", details=f"Восстановлен файл: {filename}; страховочная копия: {safety_file.name}")
        messages.success(request, f"База восстановлена из {filename}. Страховочная копия: {safety_file.name}.")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        ActionLog.objects.create(user=request.user, action="backup_restore_error", details=str(exc)[:500])
        messages.error(request, f"Не удалось восстановить базу: {exc}")
    return redirect("backup_list")


@login_required
def action_log_list(request):
    if not _admin_only(request):
        return HttpResponseForbidden("Журнал действий доступен только администратору.")
    logs = ActionLog.objects.select_related("user", "order", "old_status", "new_status")
    user_id = request.GET.get("user", "").strip()
    order_number = request.GET.get("order", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if user_id.isdigit():
        logs = logs.filter(user_id=int(user_id))
    if order_number:
        logs = logs.filter(order__order_number__icontains=order_number)
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    return render(request, "core/action_log.html", {"logs": logs[:500], "users": AppUser.objects.order_by("full_name"), "filters": {"user": user_id, "order": order_number, "date_from": date_from, "date_to": date_to}})

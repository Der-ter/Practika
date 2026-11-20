"""Журнал входов и блокировка после неудачных попыток (ЗИ-03, ЗИ-08)."""
from datetime import timedelta

from django.utils import timezone

from core.models import ActionLog

MAX_FAILS = 5
WINDOW = timedelta(minutes=15)


def write_log(user, action, details=None):
    ActionLog.objects.create(user=user, action=action, details=(details or "")[:500] or None)


def is_locked(login):
    """True, если за последние 15 минут было 5 неудачных попыток входа с этим логином."""
    failures = ActionLog.objects.filter(action="login_failed", details=login)
    last_ok = (
        ActionLog.objects.filter(action="login_ok", details=login)
        .order_by("-created_at").first()
    )
    if last_ok:
        failures = failures.filter(created_at__gt=last_ok.created_at)
    latest = list(failures.order_by("-created_at")[:MAX_FAILS])
    if len(latest) < MAX_FAILS:
        return False
    newest, oldest = latest[0].created_at, latest[-1].created_at
    return newest - oldest <= WINDOW and timezone.now() - newest < WINDOW

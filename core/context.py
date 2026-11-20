"""Данные, доступные во всех шаблонах."""
from core.version import APP_VERSION


def app_info(request):
    return {"app_version": APP_VERSION}

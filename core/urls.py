"""Маршруты приложения core."""
from django.urls import path

from core.views import auth, orders

urlpatterns = [
    path("", orders.order_list, name="orders"),
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("password/", auth.password_change, name="password_change"),
]

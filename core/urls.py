"""Маршруты приложения core."""
from django.urls import path

from core.views import auth, order_card, orders

urlpatterns = [
    path("", orders.order_list, name="orders"),
    path("orders/new/", orders.order_create, name="order_create"),
    path("clients/new/", orders.client_create, name="client_create"),
    path("orders/<int:pk>/", order_card.order_detail, name="order_detail"),
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("password/", auth.password_change, name="password_change"),
]

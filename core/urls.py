"""Маршруты приложения core."""
from django.urls import path

from core.views import auth, order_card, orders, reports

urlpatterns = [
    path("", orders.order_list, name="orders"),
    path("reports/orders/", reports.order_report, name="order_report"),
    path("orders/new/", orders.order_create, name="order_create"),
    path("clients/", orders.client_list, name="client_list"),
    path("clients/new/", orders.client_create, name="client_create"),
    path("clients/<int:pk>/edit/", orders.client_edit, name="client_edit"),
    path("orders/<int:pk>/edit/", orders.order_edit, name="order_edit"),
    path("orders/<int:pk>/", order_card.order_detail, name="order_detail"),
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("password/", auth.password_change, name="password_change"),
]

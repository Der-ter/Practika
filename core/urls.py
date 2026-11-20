"""Маршруты приложения core."""
from django.urls import path

from core.views import admin_tools, auth, order_card, orders, reports, maintenance

urlpatterns = [
    path("", orders.order_list, name="orders"),
    path("reports/orders/", reports.order_report, name="order_report"),
    path("admin-tools/users/", admin_tools.user_list, name="user_list"),
    path("admin-tools/users/new/", admin_tools.user_create, name="user_create"),
    path("admin-tools/users/<int:pk>/edit/", admin_tools.user_edit, name="user_edit"),
    path("admin-tools/references/", admin_tools.reference_list, name="reference_list"),
    path("admin-tools/references/products/new/", admin_tools.product_type_create, name="product_type_create"),
    path("admin-tools/references/products/<int:pk>/edit/", admin_tools.product_type_edit, name="product_type_edit"),
    path("admin-tools/references/materials/new/", admin_tools.material_create, name="material_create"),
    path("admin-tools/references/materials/<int:pk>/edit/", admin_tools.material_edit, name="material_edit"),
    path("orders/new/", orders.order_create, name="order_create"),
    path("clients/", orders.client_list, name="client_list"),
    path("clients/new/", orders.client_create, name="client_create"),
    path("clients/<int:pk>/edit/", orders.client_edit, name="client_edit"),
    path("orders/<int:pk>/edit/", orders.order_edit, name="order_edit"),
    path("orders/<int:pk>/", order_card.order_detail, name="order_detail"),
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),
    path("password/", auth.password_change, name="password_change"),
    path("admin-tools/backups/", maintenance.backup_list, name="backup_list"),
    path("admin-tools/backups/create/", maintenance.backup_create, name="backup_create"),
    path("admin-tools/backups/restore/", maintenance.backup_restore, name="backup_restore"),
    path("admin-tools/action-log/", maintenance.action_log_list, name="action_log_list"),
]

"""Видимость данных по ролям (ФТ-23). Проверка выполняется на сервере."""
from core.models import Order, RoleCode


def visible_orders(user):
    """Заказы, доступные пользователю."""
    code = user.role.code
    orders = Order.objects.all()
    if code == RoleCode.ADMIN:
        return orders
    if code == RoleCode.MANAGER:
        return orders.filter(manager=user)
    if code == RoleCode.DESIGNER:
        return orders.filter(designer=user)
    if code == RoleCode.EXECUTOR:
        return orders.filter(runs__executor=user).distinct()
    return orders.none()

"""
Начальные данные справочников (роли, статусы) и представление v_order_report.
"""

from django.db import migrations

ROLES = [
    ("admin", "Администратор"),
    ("manager", "Менеджер по заказам"),
    ("designer", "Дизайнер-верстальщик"),
    ("executor", "Исполнитель"),
]

# (код, наименование, порядок, конечный)
STATUSES = [
    ("new", "Новый", 1, False),
    ("layout_approval", "На согласовании макета", 2, False),
    ("in_production", "В производстве", 3, False),
    ("ready", "Готов", 4, False),
    ("issued", "Выдан", 5, True),
    ("cancelled", "Отменён", 6, True),
]

CREATE_VIEW = """
CREATE VIEW v_order_report AS
SELECT
    date_trunc('month', o.created_at)::date AS report_month,
    o.status_id                             AS status_id,
    s.name                                  AS status_name,
    COUNT(*)::integer                       AS orders_count,
    SUM(o.agreed_price)::numeric(12, 2)     AS total_price,
    (COUNT(*) FILTER (
        WHERE o.due_date < CURRENT_DATE AND NOT s.is_final
    ))::integer                             AS overdue_count
FROM orders o
JOIN order_status s ON s.status_id = o.status_id
GROUP BY 1, 2, 3;
"""

DROP_VIEW = "DROP VIEW IF EXISTS v_order_report;"


def load_reference_data(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    OrderStatus = apps.get_model("core", "OrderStatus")
    for code, name in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name})
    for code, name, sort_order, is_final in STATUSES:
        OrderStatus.objects.update_or_create(
            code=code,
            defaults={"name": name, "sort_order": sort_order, "is_final": is_final},
        )


def remove_reference_data(apps, schema_editor):
    Role = apps.get_model("core", "Role")
    OrderStatus = apps.get_model("core", "OrderStatus")
    Role.objects.filter(code__in=[c for c, _ in ROLES]).delete()
    OrderStatus.objects.filter(code__in=[s[0] for s in STATUSES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(load_reference_data, remove_reference_data),
        migrations.RunSQL(CREATE_VIEW, reverse_sql=DROP_VIEW),
    ]

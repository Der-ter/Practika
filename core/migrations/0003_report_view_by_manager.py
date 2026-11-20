"""Добавляет разрез по менеджеру в представление отчёта (ФТ-09)."""
from django.db import migrations

CREATE_VIEW = """
CREATE VIEW v_order_report AS
SELECT
    date_trunc('month', o.created_at)::date AS report_month,
    o.status_id AS status_id,
    s.name AS status_name,
    o.manager_id AS manager_id,
    COUNT(*)::integer AS orders_count,
    SUM(o.agreed_price)::numeric(12, 2) AS total_price,
    (COUNT(*) FILTER (WHERE o.due_date < CURRENT_DATE AND NOT s.is_final))::integer AS overdue_count
FROM orders o
JOIN order_status s ON s.status_id = o.status_id
GROUP BY 1, 2, 3, 4;
"""

class Migration(migrations.Migration):
    dependencies = [("core", "0002_reference_data_and_report_view")]
    operations = [
        migrations.RunSQL("DROP VIEW IF EXISTS v_order_report;", reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(CREATE_VIEW, reverse_sql="DROP VIEW IF EXISTS v_order_report;"),
    ]

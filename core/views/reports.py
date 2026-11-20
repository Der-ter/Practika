"""Отчёты по заказам и выгрузка CSV/XLSX (ФТ-09)."""
import csv
from datetime import date
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from core.models import RoleCode

HEADERS = ["Месяц", "Статус", "Количество заказов", "Сумма стоимости", "Просрочено"]

def _report_rows(user, date_from, date_to):
    """Читает агрегаты из v_order_report с ограничением менеджера."""
    sql = """
        SELECT report_month, status_name, orders_count, total_price, overdue_count
        FROM v_order_report
        WHERE report_month >= %s AND report_month <= %s
    """
    params = [date_from.replace(day=1), date_to.replace(day=1)]
    if user.role.code == RoleCode.MANAGER:
        sql += " AND manager_id = %s"
        params.append(user.pk)
    sql += " ORDER BY report_month, status_id"
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()

@login_required
def order_report(request):
    """Показывает отчёт по месяцам и статусам менеджеру или администратору."""
    if request.user.role.code not in (RoleCode.MANAGER, RoleCode.ADMIN):
        return HttpResponseForbidden("Отчёты доступны менеджеру и администратору.")
    today = timezone.localdate()
    default_from = today.replace(day=1, month=1)
    raw_from = request.GET.get("date_from", str(default_from))
    raw_to = request.GET.get("date_to", str(today))
    date_from, date_to = parse_date(raw_from), parse_date(raw_to)
    error = None
    rows = []
    if not date_from or not date_to:
        error = "Укажите корректные даты начала и окончания периода."
    elif date_from > date_to:
        error = "Дата начала периода не может быть позже даты окончания."
    else:
        rows = _report_rows(request.user, date_from, date_to)
    chart = []
    totals = {}
    for month, status, count, amount, overdue in rows:
        totals[status] = totals.get(status, 0) + count
    max_count = max(totals.values(), default=0)
    for status, count in totals.items():
        chart.append({"status": status, "count": count, "width": round(count * 100 / max_count) if max_count else 0})
    context = {"rows": rows, "chart": chart, "date_from": raw_from, "date_to": raw_to, "error": error, "total_orders": sum(r[2] for r in rows), "total_price": sum((r[3] or 0) for r in rows), "total_overdue": sum(r[4] for r in rows)}
    if request.GET.get("export") == "csv" and not error:
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="printuchet_report.csv"'
        writer = csv.writer(response, delimiter=";", lineterminator="\r\n")
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow([row[0].strftime("%m.%Y"), row[1], row[2], f"{row[3]:.2f}", row[4]])
        return response
    if request.GET.get("export") == "xlsx" and not error:
        book = Workbook()
        sheet = book.active
        sheet.title = "Заказы по месяцам"
        sheet.append(HEADERS)
        for row in rows:
            sheet.append([row[0].strftime("%m.%Y"), row[1], row[2], float(row[3] or 0), row[4]])
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="24476B")
        for column, width in {"A": 14, "B": 26, "C": 22, "D": 20, "E": 16}.items():
            sheet.column_dimensions[column].width = width
        output = BytesIO()
        book.save(output)
        response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="printuchet_report.xlsx"'
        return response
    return render(request, "core/order_report.html", context)

"""Список заказов с поиском и фильтрацией (ФТ-03, ФТ-26)."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.shortcuts import render
from django.utils import timezone

from core.forms import OrderFilterForm
from core.models import PrintRun
from core.services.access import visible_orders

PAGE_SIZE = 20  # ЭХ-01: первая страница, 20 записей


def _filtered(orders, data):
    if data.get("number"):
        orders = orders.filter(order_number__icontains=data["number"])
    if data.get("client"):
        orders = orders.filter(client__name__icontains=data["client"])
    if data.get("product"):
        orders = orders.filter(runs__product_type__name__icontains=data["product"])
    if data.get("status"):
        orders = orders.filter(status=data["status"])
    if data.get("due"):
        orders = orders.filter(due_date__lte=data["due"])
    if data.get("executor"):
        name = data["executor"]
        orders = orders.filter(
            Q(designer__full_name__icontains=name)
            | Q(runs__executor__full_name__icontains=name)
        )
    return orders.distinct()


@login_required
def order_list(request):
    form = OrderFilterForm(request.GET or None)
    orders = (
        visible_orders(request.user)
        .select_related("client", "status", "designer")
        .prefetch_related(
            Prefetch("runs", queryset=PrintRun.objects.select_related("product_type", "executor"))
        )
    )
    if form.is_valid():
        orders = _filtered(orders, form.cleaned_data)

    page = Paginator(orders, PAGE_SIZE).get_page(request.GET.get("page"))

    today = timezone.localdate()
    for order in page:
        runs = list(order.runs.all())
        order.products = ", ".join(dict.fromkeys(r.product_type.name for r in runs))
        order.executors = ", ".join(
            dict.fromkeys(r.executor.full_name for r in runs if r.executor)
        )
        # ФТ-26: срок прошёл, а статус не конечный
        order.is_overdue = order.due_date < today and not order.status.is_final

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "core/order_list.html", {
        "form": form,
        "page": page,
        "querystring": params.urlencode(),
        "can_create": request.user.role.code == "manager",
    })

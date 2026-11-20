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


# ---------------------------------------------------------------------------
# Создание клиента и заказа (ФТ-06—ФТ-08)
import uuid
from decimal import Decimal
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import timezone

from core.forms import ClientForm, OrderCreateForm, PrintRunFormSet
from core.models import ActionLog, Client, Order, OrderStatus, RoleCode


@login_required
def client_create(request):
    if request.user.role.code != RoleCode.MANAGER:
        return HttpResponseForbidden("Создавать клиентов может только менеджер.")
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = Client.objects.create(**form.cleaned_data)
        ActionLog.objects.create(user=request.user, action="client_create",
                                 details=f"Клиент: {client.name}")
        messages.success(request, f"Клиент «{client.name}» создан.")
        return redirect("order_create")
    return render(request, "core/client_form.html", {"form": form})


@login_required
def order_create(request):
    if request.user.role.code != RoleCode.MANAGER:
        return HttpResponseForbidden("Создавать заказы может только менеджер.")

    order_form = OrderCreateForm(request.POST or None)
    draft = Order()
    run_formset = PrintRunFormSet(request.POST or None, instance=draft, prefix="runs")

    if request.method == "POST":
        if order_form.is_valid() and run_formset.is_valid():
            due_date = order_form.cleaned_data["due_date"]
            if due_date < timezone.localdate():
                order_form.add_error("due_date", "Срок готовности не может быть в прошлом.")
            else:
                with transaction.atomic():
                    status = OrderStatus.objects.get(code="new")
                    order = Order.objects.create(
                        order_number=f"TMP-{uuid.uuid4().hex[:12]}",  # временный номер: 16 символов (max_length=20)
                        client=order_form.cleaned_data["client"],
                        manager=request.user,
                        status=status,
                        due_date=due_date,
                        agreed_price=order_form.cleaned_data["agreed_price"],
                    )
                    order.order_number = f"{timezone.localdate():%Y}-{order.pk:06d}"
                    order.save(update_fields=["order_number"])
                    run_formset.instance = order
                    run_formset.save()
                    ActionLog.objects.create(
                        user=request.user, order=order, action="order_create",
                        details=f"Создано тиражей: {order.runs.count()}",
                    )
                messages.success(request, f"Заказ {order.order_number} создан.")
                return redirect("order_detail", pk=order.pk)

    return render(request, "core/order_form.html", {
        "form": order_form, "run_formset": run_formset,
    })

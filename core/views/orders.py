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
        order.can_edit = (
            request.user.role.code == "manager"
            and order.manager_id == request.user.pk
            and order.status.code in ("new", "layout_approval")
        )

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "core/order_list.html", {
        "form": form,
        "page": page,
        "querystring": params.urlencode(),
        "can_create": request.user.role.code == "manager",
        "can_edit_orders": request.user.role.code == "manager",
    })


# ---------------------------------------------------------------------------
# Создание клиента и заказа (ФТ-06—ФТ-08)
import uuid
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

from core.forms import ClientForm, OrderCreateForm, OrderEditForm, PrintRunFormSet
from core.models import ActionLog, Client, Order, OrderStatus, RoleCode


def _can_manage_clients(user):
    """Клиентский справочник доступен менеджеру и администратору."""
    return user.role.code in (RoleCode.MANAGER, RoleCode.ADMIN)


@login_required
def client_list(request):
    """Список клиентов доступен менеджеру и администратору (ФТ-06)."""
    if not _can_manage_clients(request.user):
        return HttpResponseForbidden("Просматривать клиентов может только менеджер или администратор.")
    clients = Client.objects.all().order_by("name", "id")
    return render(request, "core/client_list.html", {"clients": clients})


@login_required
def client_create(request):
    if not _can_manage_clients(request.user):
        return HttpResponseForbidden("Создавать клиентов может только менеджер или администратор.")
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        duplicate_exists = Client.objects.filter(phone=phone).exists()
        client = Client.objects.create(**form.cleaned_data)
        ActionLog.objects.create(
            user=request.user, action="client_create", details=f"Клиент: {client.name}"
        )
        if duplicate_exists:
            messages.warning(
                request, "Внимание: клиент с таким телефоном уже существует. "
                         "Новая запись всё равно сохранена."
            )
        messages.success(request, f"Клиент «{client.name}» создан.")
        return redirect("client_list")
    return render(request, "core/client_form.html", {
        "form": form, "page_title": "Новый клиент", "cancel_url": "client_list",
    })


@login_required
def client_edit(request, pk):
    """Изменение реквизитов клиента менеджером или администратором (ФТ-06)."""
    if not _can_manage_clients(request.user):
        return HttpResponseForbidden("Изменять клиентов может только менеджер или администратор.")
    client = get_object_or_404(Client, pk=pk)
    initial = {
        "client_type": client.client_type,
        "name": client.name,
        "contact_person": client.contact_person,
        "phone": client.phone,
        "email": client.email,
    }
    form = ClientForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        duplicate_exists = Client.objects.filter(phone=phone).exclude(pk=client.pk).exists()
        old_name = client.name
        for field, value in form.cleaned_data.items():
            setattr(client, field, value)
        client.save(update_fields=list(form.cleaned_data.keys()))
        ActionLog.objects.create(
            user=request.user, action="client_edit",
            details=f"Изменён клиент: {old_name} → {client.name}",
        )
        if duplicate_exists:
            messages.warning(
                request, "Внимание: другой клиент уже использует этот телефон. "
                         "Изменения сохранены."
            )
        messages.success(request, f"Данные клиента «{client.name}» обновлены.")
        return redirect("client_list")
    return render(request, "core/client_form.html", {
        "form": form, "page_title": "Изменить клиента", "cancel_url": "client_list",
        "client": client,
    })


@login_required
def order_edit(request, pk):
    """Редактирование заказа владельцем-менеджером в разрешённых статусах (ФТ-08)."""
    if request.user.role.code != RoleCode.MANAGER:
        return HttpResponseForbidden("Редактировать заказы может только менеджер.")

    order = get_object_or_404(Order.objects.select_related("status", "client"),
                              pk=pk, manager=request.user)
    if order.status.code not in ("new", "layout_approval"):
        messages.error(request, "Редактирование этого заказа уже недоступно.")
        return redirect("order_detail", pk=order.pk)

    order_form = OrderEditForm(
        request.POST or None, order=order,
        initial={"due_date": order.due_date, "agreed_price": order.agreed_price},
    )
    can_edit_runs = order.status.code == "new"
    run_formset = None
    if can_edit_runs:
        run_formset = PrintRunFormSet(
            request.POST or None, instance=order, prefix="runs",
        )

    if request.method == "POST":
        forms_valid = order_form.is_valid()
        if can_edit_runs:
            forms_valid = run_formset.is_valid() and forms_valid
        posted_version = request.POST.get("row_version", "")
        if not posted_version.isdigit() or int(posted_version) != order.row_version:
            messages.error(request, "Заказ уже изменился. Обновите страницу и повторите сохранение.")
        elif forms_valid:
            with transaction.atomic():
                locked = Order.objects.select_for_update().get(pk=order.pk, manager=request.user)
                if locked.row_version != int(posted_version) or locked.status.code != order.status.code:
                    messages.error(request, "Заказ уже изменился. Обновите страницу и повторите сохранение.")
                    return redirect("order_edit", pk=order.pk)
                locked.due_date = order_form.cleaned_data["due_date"]
                locked.agreed_price = order_form.cleaned_data["agreed_price"]
                locked.row_version += 1
                locked.save(update_fields=["due_date", "agreed_price", "row_version"])
                if can_edit_runs:
                    run_formset.instance = locked
                    run_formset.save()
                ActionLog.objects.create(
                    user=request.user, order=locked, action="order_edit",
                    details="Изменены данные заказа" + (" и тиражи" if can_edit_runs else ""),
                )
            messages.success(request, f"Заказ {order.order_number} обновлён.")
            return redirect("order_detail", pk=order.pk)

    return render(request, "core/order_edit.html", {
        "order": order, "form": order_form, "run_formset": run_formset,
        "can_edit_runs": can_edit_runs,
    })


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

"""Карточка заказа и действия над ним (ФТ-04, ФТ-05, ФТ-10…ФТ-16, ФТ-22, ЗИ-06)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from core.models import ActionLog, AppUser, OrderComment, RoleCode
from core.services import transitions as tr
from core.services.access import visible_orders
from core.services.login_guard import write_log


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dispatch(request, order, action):
    user, post = request.user, request.POST
    if action == "comment":
        return tr.add_comment(order.pk, user, post.get("kind", "regular"), post.get("body", ""))
    if action == "produce":
        return tr.mark_produced(order.pk, user, _int(post.get("run_id")))

    version = _int(post.get("row_version"))
    if version is None:
        raise tr.TransitionError("Страница устарела. Обновите её и повторите действие.")
    if action == "submit":
        executors = {run.pk: _int(post.get(f"executor_{run.pk}")) for run in order.runs.all()}
        return tr.submit_to_layout(order.pk, user, version, _int(post.get("designer")), executors)
    if action == "save_layout":
        return tr.save_layout(order.pk, user, version, post.get("layout_link"))
    if action == "approve":
        return tr.approve_layout(order.pk, user, version)
    if action == "ready":
        return tr.finish_production(order.pk, user, version)
    if action == "issue":
        return tr.issue_order(order.pk, user, version, post.get("invoice_number"))
    if action == "cancel":
        return tr.cancel_order(order.pk, user, version, post.get("cancel_reason"))
    raise tr.TransitionError("Неизвестное действие.")


def _history_text(entry):
    if entry.action == "order_create":
        return "Заказ создан"
    if entry.action == "order_edit":
        return entry.details or "Данные заказа изменены"
    if entry.action == "status_change":
        return f"Статус: {entry.old_status} → {entry.new_status}"
    if entry.action == "layout_link":
        return "Указан путь к макету"
    if entry.action == "run_produced":
        return "Отмечено изготовление тиража"
    return entry.action


def _context(request, order, posted):
    user = request.user
    role = user.role.code
    status = order.status.code
    runs = list(order.runs.select_related("product_type", "material", "executor"))

    owner_manager = role == RoleCode.MANAGER and order.manager_id == user.id
    owner_designer = role == RoleCode.DESIGNER and order.designer_id == user.id
    can_submit = owner_manager and status == "new"
    can_edit_order = owner_manager and status in ("new", "layout_approval")
    is_my_executor = role == RoleCode.EXECUTOR and any(r.executor_id == user.id for r in runs)

    for run in runs:
        run.can_mark = (
            role == RoleCode.EXECUTOR and status == "in_production"
            and run.executor_id == user.id and not run.produced_at
        )

    history = [
        {"at": e.created_at, "who": e.user.full_name if e.user else "—", "text": _history_text(e)}
        for e in ActionLog.objects.filter(order=order)
        .exclude(action__in=["access_denied"])
        .select_related("user", "old_status", "new_status").order_by("created_at", "id")
    ]

    kinds = [(OrderComment.Kind.REGULAR.value, OrderComment.Kind.REGULAR.label)]
    if role in (RoleCode.MANAGER, RoleCode.DESIGNER):
        kinds += [(k.value, k.label) for k in (OrderComment.Kind.REMARKS, OrderComment.Kind.APPROVAL)]

    ctx = {
        "order": order,
        "runs": runs,
        "total_quantity": sum(r.quantity for r in runs),
        "is_overdue": order.due_date < timezone.localdate() and not order.status.is_final,
        "comments": order.comments.select_related("author__role"),
        "history": history,
        "comment_kinds": kinds,
        "posted": posted,
        # права для интерфейса; настоящая проверка — в services.transitions
        "can_submit": can_submit,
        "can_edit_order": can_edit_order,
        "can_cancel": owner_manager and status in ("new", "layout_approval"),
        "can_issue": owner_manager and status == "ready",
        "can_edit_layout": owner_designer and status == "layout_approval",
        "can_approve": owner_designer and status == "layout_approval",
        "can_finish": is_my_executor and status == "in_production",
        # ЗИ-06: контакты клиента получают только менеджер и администратор
        "show_contacts": role in (RoleCode.MANAGER, RoleCode.ADMIN),
    }
    ctx["has_actions"] = any(ctx[k] for k in (
        "can_submit", "can_cancel", "can_issue", "can_approve", "can_finish"))
    if can_submit:
        ctx["designers"] = AppUser.objects.filter(role__code=RoleCode.DESIGNER, is_blocked=False)
        ctx["executors"] = AppUser.objects.filter(role__code=RoleCode.EXECUTOR, is_blocked=False)
    return ctx


@login_required
def order_detail(request, pk):
    user = request.user
    order = (
        visible_orders(user).filter(pk=pk)
        .select_related("client", "status", "manager", "designer").first()
    )
    if order is None:
        # ФТ-23: чужой или несуществующий заказ недоступен и по прямой ссылке
        write_log(user, "access_denied", f"заказ {pk}")
        raise Http404

    posted = {}
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            messages.success(request, _dispatch(request, order, action))
            return redirect("order_detail", pk=pk)
        except tr.AccessDenied as error:
            write_log(user, "access_denied", f"{action}: заказ {pk}")
            messages.error(request, str(error))
        except tr.TransitionError as error:
            messages.error(request, str(error))
        posted = request.POST  # введённые данные не теряются (ПИ-05)

    return render(request, "core/order_detail.html", _context(request, order, posted))

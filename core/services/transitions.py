"""
Бизнес-логика заказа: переходы статусов П1–П7, макет, изготовление, комментарии.
Все проверки прав и условий выполняются здесь, на сервере (ЗИ-05, ФТ-22).
Смена статуса и запись в историю идут в одной транзакции (НТ-03);
одновременное изменение отслеживается по row_version (НТ-04).
"""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from core.models import (
    ActionLog, AppUser, Order, OrderComment, OrderStatus, PrintRun, RoleCode,
)


class TransitionError(Exception):
    """Операция отклонена: не выполнено условие. Текст показывается пользователю."""


class AccessDenied(TransitionError):
    """Операция отклонена: у роли нет права. Попытка записывается в журнал."""


# ---------------------------------------------------------------- служебное

def _load(order_id):
    # блокируем только строку заказа (у роли приложения нет UPDATE на справочник статусов)
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("status").get(pk=order_id)
    )
    return order


def _status(code):
    return OrderStatus.objects.get(code=code)


def _log(user, order, action, old=None, new=None, details=None):
    ActionLog.objects.create(
        user=user, order=order, action=action, old_status=old, new_status=new,
        details=details,
    )


def _bump(order, version, **fields):
    """Изменяет заказ, только если его версия не изменилась (НТ-04)."""
    updated = Order.objects.filter(pk=order.pk, row_version=version).update(
        row_version=F("row_version") + 1, **fields
    )
    if not updated:
        raise TransitionError(
            "Заказ был изменён другим пользователем. Обновите страницу и повторите действие."
        )


def _need_manager(order, user):
    if user.role.code != RoleCode.MANAGER or order.manager_id != user.id:
        raise AccessDenied("Операция доступна только менеджеру, создавшему заказ.")


def _need_designer(order, user):
    if user.role.code != RoleCode.DESIGNER or order.designer_id != user.id:
        raise AccessDenied("Операция доступна только дизайнеру, назначенному на заказ.")


def _need_status(order, *codes, message):
    if order.status.code not in codes:
        raise TransitionError(message)


def _change_status(user, order, version, new_code, **fields):
    new_status = _status(new_code)
    old_status = order.status
    _bump(order, version, status=new_status, **fields)
    _log(user, order, "status_change", old_status, new_status)


# ---------------------------------------------------------------- переходы

@transaction.atomic
def submit_to_layout(order_id, user, version, designer_id, executor_ids):
    """П1: Новый → На согласовании макета (менеджер)."""
    order = _load(order_id)
    _need_manager(order, user)
    _need_status(order, "new", message="Передать в работу можно только заказ в статусе «Новый».")
    runs = list(order.runs.select_related("product_type"))
    if not runs:
        raise TransitionError("Добавьте в заказ хотя бы один тираж.")

    designer = None
    if designer_id:
        designer = AppUser.objects.filter(
            pk=designer_id, role__code=RoleCode.DESIGNER, is_blocked=False).first()
    if designer is None:
        raise TransitionError("Выберите дизайнера-верстальщика.")

    for run in runs:
        executor = None
        if executor_ids.get(run.pk):
            executor = AppUser.objects.filter(
                pk=executor_ids[run.pk], role__code=RoleCode.EXECUTOR, is_blocked=False).first()
        if executor is None:
            raise TransitionError(
                f"Назначьте исполнителя для тиража «{run.product_type.name}, {run.format}».")
        run.executor = executor

    for run in runs:
        run.save(update_fields=["executor"])
    _change_status(user, order, version, "layout_approval", designer=designer)
    return "Заказ передан на согласование макета."


@transaction.atomic
def approve_layout(order_id, user, version):
    """П3: На согласовании макета → В производстве (дизайнер)."""
    order = _load(order_id)
    _need_designer(order, user)
    _need_status(order, "layout_approval",
                 message="Перевести в производство можно заказ в статусе «На согласовании макета».")
    if not order.layout_link:
        raise TransitionError("Сначала укажите ссылку или путь к макету.")
    if not order.comments.filter(kind=OrderComment.Kind.APPROVAL).exists():
        raise TransitionError(
            "Добавьте комментарий вида «Согласие»: он подтверждает согласие заказчика.")
    _change_status(user, order, version, "in_production")
    return "Заказ передан в производство."


@transaction.atomic
def finish_production(order_id, user, version):
    """П4: В производстве → Готов (исполнитель)."""
    order = _load(order_id)
    if user.role.code != RoleCode.EXECUTOR or not order.runs.filter(executor=user).exists():
        raise AccessDenied("Операция доступна только исполнителю, которому назначен тираж заказа.")
    _need_status(order, "in_production",
                 message="Перевести в «Готов» можно заказ в статусе «В производстве».")
    if order.runs.filter(produced_at__isnull=True).exists():
        raise TransitionError("У всех тиражей должна быть отмечена дата изготовления.")
    _change_status(user, order, version, "ready")
    return "Заказ готов к выдаче."


@transaction.atomic
def issue_order(order_id, user, version, invoice_number):
    """П5: Готов → Выдан (менеджер, по накладной)."""
    order = _load(order_id)
    _need_manager(order, user)
    _need_status(order, "ready", message="Выдать можно только заказ в статусе «Готов».")
    invoice = (invoice_number or "").strip()
    if not invoice:
        raise TransitionError("Укажите номер накладной.")
    if len(invoice) > 30:
        raise TransitionError("Номер накладной не длиннее 30 символов.")
    _change_status(user, order, version, "issued", invoice_number=invoice)
    return "Выдача оформлена."


@transaction.atomic
def cancel_order(order_id, user, version, reason):
    """П6, П7: Новый или На согласовании макета → Отменён (менеджер)."""
    order = _load(order_id)
    _need_manager(order, user)
    _need_status(order, "new", "layout_approval",
                 message="Отменить можно заказ в статусе «Новый» или «На согласовании макета».")
    reason = (reason or "").strip()
    if not 1 <= len(reason) <= 300:
        raise TransitionError("Причина отмены: от 1 до 300 символов.")
    _change_status(user, order, version, "cancelled", cancel_reason=reason)
    return "Заказ отменён."


# ---------------------------------------------------------------- прочие действия

@transaction.atomic
def save_layout(order_id, user, version, link):
    """Ссылка на макет (дизайнер, статус «На согласовании макета»)."""
    order = _load(order_id)
    _need_designer(order, user)
    _need_status(order, "layout_approval",
                 message="Ссылку на макет можно изменять в статусе «На согласовании макета».")
    link = (link or "").strip()
    if not 1 <= len(link) <= 500:
        raise TransitionError("Путь к макету: от 1 до 500 символов.")
    _bump(order, version, layout_link=link)
    _log(user, order, "layout_link")
    return "Путь к макету сохранён."


@transaction.atomic
def mark_produced(order_id, user, run_id):
    """Отметка изготовления тиража (исполнитель)."""
    order = _load(order_id)
    run = order.runs.filter(pk=run_id).first()
    if user.role.code != RoleCode.EXECUTOR or run is None or run.executor_id != user.id:
        raise AccessDenied("Отметить можно только назначенный вам тираж.")
    _need_status(order, "in_production",
                 message="Изготовление отмечается в статусе «В производстве».")
    if run.produced_at:
        raise TransitionError("Изготовление этого тиража уже отмечено.")
    PrintRun.objects.filter(pk=run.pk).update(produced_at=timezone.now())
    _log(user, order, "run_produced", details=f"тираж {run.pk}")
    return "Изготовление тиража отмечено."


@transaction.atomic
def add_comment(order_id, user, kind, body):
    """Комментарий к заказу (ФТ-05): нельзя изменить и удалить."""
    order = Order.objects.get(pk=order_id)
    if kind not in OrderComment.Kind.values:
        raise TransitionError("Неизвестный тип комментария.")
    if kind != OrderComment.Kind.REGULAR and user.role.code not in (
            RoleCode.MANAGER, RoleCode.DESIGNER):
        raise AccessDenied("Комментарии «Замечания» и «Согласие» оставляют менеджер и дизайнер.")
    body = (body or "").strip()
    if not 1 <= len(body) <= 2000:
        raise TransitionError("Комментарий: от 1 до 2000 символов.")
    OrderComment.objects.create(order=order, author=user, kind=kind, body=body)
    return "Комментарий добавлен."

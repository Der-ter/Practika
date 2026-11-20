"""
Тестовые данные для прототипа «ПринтУчёт» (задание: 3–5 пользователей, 10–15 заказов).
Все данные вымышленные (152-ФЗ). Команда безопасна для повторного запуска:
существующие записи не дублируются.

Запуск:  python manage.py seed_demo
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    ActionLog, AppUser, Client, Material, Order, OrderComment, OrderStatus,
    PrintRun, ProductType, Role, RoleCode,
)

DEMO_PASSWORD = "Print2026"  # только для тестовых учётных записей


def dt(month, day, hour=10, minute=0, year=2026):
    return timezone.make_aware(datetime(year, month, day, hour, minute))


USERS = [
    ("manager1", "Анна Смирнова", RoleCode.MANAGER),
    ("manager2", "Олег Фёдоров", RoleCode.MANAGER),
    ("designer1", "Мария Орлова", RoleCode.DESIGNER),
    ("executor1", "Иван Петров", RoleCode.EXECUTOR),
]

CLIENTS = {
    "coffee": ("legal", "ООО «Урал Кофе»", "Павел Воронин", "+7 (343) 212-45-67", "center@uralcoffee.example"),
    "city": ("legal", "ООО «СитиСтрой»", "Елена Мартынова", "+7 (343) 310-22-18", "office@citystroy.example"),
    "zakh": ("legal", "ИП Захаров А. В.", None, "+7 (912) 604-18-30", None),
    "school": ("legal", "МАОУ СОШ № 14", "Татьяна Нестерова", "+7 (343) 255-90-14", "school14@example.org"),
    "ivanova": ("person", "Крылова Ирина Сергеевна", None, "+7 (922) 188-47-05", None),
    "dent": ("legal", "ООО «Белый кедр»", "Игорь Лазарев", "+7 (343) 379-61-52", "info@belkedr.example"),
}

PRODUCT_TYPES = ["Визитки", "Листовки", "Буклеты", "Брошюры", "Плакаты"]

MATERIALS = [
    ("Мелованная 350 г/м²", "paper", 350, True),
    ("Мелованная 150 г/м²", "paper", 150, True),
    ("Офсетная 80 г/м²", "paper", 80, True),
    ("Самоклеящаяся плёнка", "media", None, True),
    ("Картон 300 г/м² (снят с производства)", "paper", 300, False),
]

LAYOUT = "\\\\printgrad\\layouts\\2026\\{n}\\v{v}.pdf"

# Путь заказа по статусам и ответственная роль за каждый переход
PATHS = {
    "new": ["new"],
    "layout_approval": ["new", "layout_approval"],
    "in_production": ["new", "layout_approval", "in_production"],
    "ready": ["new", "layout_approval", "in_production", "ready"],
    "issued": ["new", "layout_approval", "in_production", "ready", "issued"],
    "cancelled": ["new", "layout_approval", "cancelled"],
}

# номер, клиент, менеджер, статус, создан, срок, цена, тиражи, дополнительно
# тираж: (вид, формат, количество, материал, изготовлен)
ORDERS = [
    ("2026-000140", "dent", "manager2", "issued", dt(8, 5), dt(8, 14), 18500,
     [("Буклеты", "А4, 3 сложения", 500, "Мелованная 150 г/м²", dt(8, 12, 15))],
     {"invoice": "ПГ-2026-0071"}),
    ("2026-000141", "school", "manager1", "issued", dt(8, 19), dt(9, 2), 42000,
     [("Брошюры", "А5, 24 стр.", 300, "Офсетная 80 г/м²", dt(8, 30, 16))],
     {"invoice": "ПГ-2026-0079"}),
    ("2026-000142", "zakh", "manager2", "cancelled", dt(9, 3), dt(9, 15), 9000,
     [("Визитки", "90 × 50 мм", 1000, "Мелованная 350 г/м²", None)],
     {"reason": "Заказчик отказался от тиража"}),
    ("2026-000143", "ivanova", "manager1", "issued", dt(9, 17), dt(9, 24), 3200,
     [("Плакаты", "А2", 10, "Мелованная 150 г/м²", dt(9, 22, 12))],
     {"invoice": "ПГ-2026-0094"}),
    ("2026-000144", "coffee", "manager1", "issued", dt(10, 6), dt(10, 15), 27500,
     [("Листовки", "А5", 3000, "Мелованная 150 г/м²", dt(10, 13, 14)),
      ("Визитки", "90 × 50 мм", 1000, "Мелованная 350 г/м²", dt(10, 13, 17))],
     {"invoice": "ПГ-2026-0102"}),
    ("2026-000145", "city", "manager1", "ready", dt(10, 20), dt(11, 25), 14800,
     [("Визитки", "90 × 50 мм", 1000, "Мелованная 350 г/м²", dt(11, 18, 13))], {}),
    ("2026-000146", "dent", "manager2", "in_production", dt(10, 27), dt(11, 10), 21000,
     [("Буклеты", "А4, 2 сложения", 700, "Мелованная 150 г/м²", None)],
     {"manager_comment": "Заказчик просит ускорить выполнение."}),
    ("2026-000147", "zakh", "manager2", "in_production", dt(11, 3), dt(11, 27), 6400,
     [("Визитки", "90 × 50 мм", 500, "Мелованная 350 г/м²", dt(11, 17, 12)),
      ("Листовки", "А6", 1000, "Мелованная 150 г/м²", None)], {}),
    ("2026-000148", "coffee", "manager1", "layout_approval", dt(10, 29), dt(11, 30), 31000,
     [("Визитки", "90 × 50 мм", 1000, "Мелованная 350 г/м²", None),
      ("Листовки", "А5", 2000, "Мелованная 150 г/м²", None)],
     {"layout": True, "version": 3}),
    ("2026-000149", "school", "manager1", "layout_approval", dt(11, 10), dt(11, 28), 55000,
     [("Брошюры", "А4, 32 стр.", 200, "Офсетная 80 г/м²", None),
      ("Плакаты", "А3", 50, "Мелованная 150 г/м²", None)],
     {"layout": True, "version": 1,
      "remarks": "Заказчик просит заменить логотип на обложке."}),
    ("2026-000150", "ivanova", "manager2", "new", dt(11, 17), dt(11, 29), 2500,
     [("Плакаты", "А3", 5, "Мелованная 150 г/м²", None)], {}),
    ("2026-000151", "city", "manager1", "new", dt(11, 19), dt(12, 5), 38000,
     [("Буклеты", "А4, 2 сложения", 1000, "Мелованная 150 г/м²", None),
      ("Листовки", "А5", 2000, "Мелованная 150 г/м²", None)], {}),
]


class Command(BaseCommand):
    help = "Создаёт тестовых пользователей, справочники, клиентов и заказы"

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {r.code: r for r in Role.objects.all()}
        statuses = {s.code: s for s in OrderStatus.objects.all()}
        if len(statuses) < 6 or len(roles) < 4:
            self.stderr.write("Справочники ролей и статусов не заполнены: выполните migrate.")
            return

        users = {u.login: u for u in AppUser.objects.all()}
        for login, name, role_code in USERS:
            if login not in users:
                users[login] = AppUser.objects.create_user(
                    login, DEMO_PASSWORD, full_name=name, role=roles[role_code],
                    password_changed_at=timezone.now(),
                )
        manager = {"manager1": users["manager1"], "manager2": users["manager2"]}
        designer, executor = users["designer1"], users["executor1"]

        products = {n: ProductType.objects.get_or_create(name=n)[0] for n in PRODUCT_TYPES}
        materials = {}
        for name, kind, gram, active in MATERIALS:
            materials[name], _ = Material.objects.get_or_create(
                name=name, defaults={"kind": kind, "grammage": gram, "is_active": active})
        clients = {}
        for key, (ctype, name, contact, phone, email) in CLIENTS.items():
            clients[key], _ = Client.objects.get_or_create(
                name=name, defaults={"client_type": ctype, "contact_person": contact,
                                     "phone": phone, "email": email})

        created = 0
        for number, ckey, mkey, status, created_at, due, price, runs, extra in ORDERS:
            if Order.objects.filter(order_number=number).exists():
                continue
            mgr = manager[mkey]
            has_designer = status != "new"
            order = Order.objects.create(
                order_number=number, client=clients[ckey], manager=mgr,
                designer=designer if has_designer else None,
                status=statuses[status], created_at=created_at,
                due_date=due.date(), agreed_price=price,
                layout_link=LAYOUT.format(n=number[-6:], v=extra.get("version", 1))
                if has_designer and status != "cancelled" else None,
                invoice_number=extra.get("invoice"),
                cancel_reason=extra.get("reason"),
            )
            for product, fmt, qty, material, produced in runs:
                PrintRun.objects.create(
                    order=order, product_type=products[product], material=materials[material],
                    executor=executor if has_designer else None,
                    format=fmt, quantity=qty, produced_at=produced,
                )
            self._history(order, status, mgr, designer, executor, created_at)
            self._comments(order, status, mgr, designer, created_at, extra)
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Готово. Новых заказов: {created}. Пароль тестовых пользователей: {DEMO_PASSWORD}"))

    def _history(self, order, status, mgr, designer, executor, created_at):
        statuses = {s.code: s for s in OrderStatus.objects.all()}
        ActionLog.objects.create(
            user=mgr, order=order, new_status=statuses["new"], action="order_create",
            details=order.order_number, created_at=created_at)
        actors = {"layout_approval": mgr, "in_production": designer,
                  "ready": executor, "issued": mgr, "cancelled": mgr}
        path = PATHS[status]
        for i in range(1, len(path)):
            ActionLog.objects.create(
                user=actors[path[i]], order=order,
                old_status=statuses[path[i - 1]], new_status=statuses[path[i]],
                action="status_change",
                created_at=created_at + timedelta(days=i, hours=i),
            )

    def _comments(self, order, status, mgr, designer, created_at, extra):
        step = timedelta(hours=5)
        if status in ("layout_approval", "in_production", "ready", "issued"):
            OrderComment.objects.create(
                order=order, author=designer, kind="regular", created_at=created_at + step,
                body="Макет подготовлен и отправлен заказчику на согласование.")
        if extra.get("remarks"):
            OrderComment.objects.create(
                order=order, author=designer, kind="remarks", created_at=created_at + 2 * step,
                body=extra["remarks"])
        if status in ("in_production", "ready", "issued"):
            OrderComment.objects.create(
                order=order, author=designer, kind="approval", created_at=created_at + 3 * step,
                body="Заказчик согласовал макет и условия.")
        if extra.get("manager_comment"):
            OrderComment.objects.create(
                order=order, author=order.manager, kind="regular", created_at=created_at + 4 * step,
                body=extra["manager_comment"])

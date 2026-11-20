from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AppUser, Client, Material, Order, OrderStatus, ProductType, Role, RoleCode,
)


class OrderCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager_role = Role.objects.get(code=RoleCode.MANAGER)
        cls.executor_role = Role.objects.get(code=RoleCode.EXECUTOR)
        cls.manager = AppUser.objects.create_user(
            login="manager_test", password="StrongPass123",
            full_name="Тестовый менеджер", role=cls.manager_role,
        )
        cls.executor = AppUser.objects.create_user(
            login="executor_test", password="StrongPass123",
            full_name="Тестовый исполнитель", role=cls.executor_role,
        )
        cls.client_record = Client.objects.create(
            client_type=Client.ClientType.LEGAL,
            name="ООО Тест", phone="+7 (900) 123-45-67",
        )
        cls.product = ProductType.objects.create(name="Визитки тест")
        cls.material = Material.objects.create(
            name="Бумага тест", kind=Material.Kind.PAPER, grammage=300,
        )
        cls.new_status = OrderStatus.objects.get(code="new")

    def test_manager_can_open_order_form(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("order_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Новый заказ")
        self.assertContains(response, "Тиражи")

    def test_manager_can_create_order_with_run(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("order_create"), {
            "client": self.client_record.pk,
            "due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "agreed_price": "12500.00",
            "runs-TOTAL_FORMS": "5",
            "runs-INITIAL_FORMS": "0",
            "runs-MIN_NUM_FORMS": "1",
            "runs-MAX_NUM_FORMS": "50",
            "runs-0-product_type": self.product.pk,
            "runs-0-format": "A4",
            "runs-0-quantity": "1000",
            "runs-0-material": self.material.pk,
        })
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(manager=self.manager)
        self.assertEqual(order.status.code, "new")
        self.assertEqual(order.agreed_price, Decimal("12500.00"))
        self.assertEqual(order.runs.count(), 1)
        self.assertTrue(order.order_number.startswith(str(timezone.localdate().year)))

    def test_non_manager_cannot_create_order(self):
        self.client.force_login(self.executor)
        response = self.client.get(reverse("order_create"))
        self.assertEqual(response.status_code, 403)

    def test_order_requires_at_least_one_run(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("order_create"), {
            "client": self.client_record.pk,
            "due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "agreed_price": "100",
            "runs-TOTAL_FORMS": "5",
            "runs-INITIAL_FORMS": "0",
            "runs-MIN_NUM_FORMS": "1",
            "runs-MAX_NUM_FORMS": "50",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)


class OrderAndClientEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager_role = Role.objects.get(code=RoleCode.MANAGER)
        cls.executor_role = Role.objects.get(code=RoleCode.EXECUTOR)
        cls.admin_role = Role.objects.get(code=RoleCode.ADMIN)
        cls.admin = AppUser.objects.create_user(
            login="admin_client_test", password="StrongPass123",
            full_name="Администратор тестирования", role=cls.admin_role,
        )
        cls.manager = AppUser.objects.create_user(
            login="manager_edit", password="StrongPass123",
            full_name="Менеджер для редактирования", role=cls.manager_role,
        )
        cls.other_manager = AppUser.objects.create_user(
            login="manager_other", password="StrongPass123",
            full_name="Другой менеджер", role=cls.manager_role,
        )
        cls.executor = AppUser.objects.create_user(
            login="executor_edit", password="StrongPass123",
            full_name="Исполнитель для редактирования", role=cls.executor_role,
        )
        cls.client_record = Client.objects.create(
            client_type=Client.ClientType.LEGAL, name="ООО Клиент редактирования",
            phone="+7 900 111-22-33",
        )
        cls.product = ProductType.objects.create(name="Буклеты тест")
        cls.material = Material.objects.create(
            name="Бумага для редактирования", kind=Material.Kind.PAPER, grammage=150,
        )
        cls.new_status = OrderStatus.objects.get(code="new")
        cls.approval_status = OrderStatus.objects.get(code="layout_approval")
        cls.ready_status = OrderStatus.objects.get(code="ready")

    def make_order(self, manager=None, status=None):
        from core.models import PrintRun
        order = Order.objects.create(
            order_number=f"2026-{Order.objects.count() + 900001:06d}",
            client=self.client_record, manager=manager or self.manager,
            status=status or self.new_status,
            due_date=timezone.localdate() + timedelta(days=10),
            agreed_price=Decimal("1500.00"),
        )
        PrintRun.objects.create(
            order=order, product_type=self.product, material=self.material,
            format="A4", quantity=100,
        )
        return order

    def test_manager_can_edit_own_new_order(self):
        order = self.make_order()
        self.client.force_login(self.manager)
        response = self.client.post(reverse("order_edit", args=[order.pk]), {
            "row_version": order.row_version,
            "due_date": (timezone.localdate() + timedelta(days=15)).isoformat(),
            "agreed_price": "2500.00",
            "runs-TOTAL_FORMS": "2", "runs-INITIAL_FORMS": "1",
            "runs-MIN_NUM_FORMS": "1", "runs-MAX_NUM_FORMS": "50",
            "runs-0-id": order.runs.get().pk,
            "runs-0-order": order.pk,
            "runs-0-product_type": self.product.pk,
            "runs-0-format": "A3", "runs-0-quantity": "200",
            "runs-0-material": self.material.pk,
            "runs-1-product_type": "", "runs-1-format": "",
            "runs-1-quantity": "", "runs-1-material": "",
        })
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.agreed_price, Decimal("2500.00"))
        self.assertEqual(order.runs.get().quantity, 200)
        self.assertEqual(order.row_version, 2)

    def test_manager_cannot_edit_another_managers_order(self):
        order = self.make_order(manager=self.other_manager)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("order_edit", args=[order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_manager_cannot_edit_order_after_new_status(self):
        order = self.make_order(status=self.ready_status)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("order_edit", args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("order_detail", args=[order.pk]))

    def test_manager_sees_edit_order_button_in_detail(self):
        order = self.make_order()
        self.client.force_login(self.manager)
        response = self.client.get(reverse("order_detail", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Изменить заказ")

    def test_admin_can_open_client_list(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("client_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Клиенты")

    def test_admin_can_create_client(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("client_create"), {
            "client_type": "person", "name": "Тестовый клиент от администратора",
            "contact_person": "", "phone": "+7 900 555-11-22", "email": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Client.objects.filter(name="Тестовый клиент от администратора").exists())

    def test_admin_can_edit_client(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("client_edit", args=[self.client_record.pk]), {
            "client_type": "legal", "name": "ООО Изменено администратором",
            "contact_person": "", "phone": "+7 900 111-22-33", "email": "",
        })
        self.assertEqual(response.status_code, 302)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.name, "ООО Изменено администратором")

    def test_manager_can_edit_client(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("client_edit", args=[self.client_record.pk]), {
            "client_type": "legal", "name": "ООО Клиент обновлённый",
            "contact_person": "Иванов", "phone": "+7 900 111-22-33", "email": "",
        })
        self.assertEqual(response.status_code, 302)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.name, "ООО Клиент обновлённый")

    def test_non_manager_cannot_open_client_list(self):
        self.client.force_login(self.executor)
        response = self.client.get(reverse("client_list"))
        self.assertEqual(response.status_code, 403)

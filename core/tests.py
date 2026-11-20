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

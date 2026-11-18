"""
Уровень данных системы «ПринтУчёт».
Модели соответствуют физической модели данных (этап 1.4, раздел 6, табл. 11–12).
Имена таблиц и столбцов в БД заданы так же, как в физической модели.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length, Now
from django.utils import timezone

# Позволяет писать в ограничениях body__length__gte=1
models.TextField.register_lookup(Length)


# ---------------------------------------------------------------------------
# Коды справочников (используются в бизнес-логике и в начальных данных)
# ---------------------------------------------------------------------------

class RoleCode(models.TextChoices):
    ADMIN = "admin", "Администратор"
    MANAGER = "manager", "Менеджер по заказам"
    DESIGNER = "designer", "Дизайнер-верстальщик"
    EXECUTOR = "executor", "Исполнитель"


class StatusCode(models.TextChoices):
    NEW = "new", "Новый"
    LAYOUT_APPROVAL = "layout_approval", "На согласовании макета"
    IN_PRODUCTION = "in_production", "В производстве"
    READY = "ready", "Готов"
    ISSUED = "issued", "Выдан"
    CANCELLED = "cancelled", "Отменён"


# ---------------------------------------------------------------------------
# Справочники
# ---------------------------------------------------------------------------

class Role(models.Model):
    id = models.AutoField(primary_key=True, db_column="role_id")
    code = models.CharField("Код", max_length=30, unique=True)
    name = models.CharField("Наименование", max_length=60, unique=True)

    class Meta:
        db_table = "role"
        verbose_name = "роль"
        verbose_name_plural = "роли"

    def __str__(self):
        return self.name


class OrderStatus(models.Model):
    id = models.AutoField(primary_key=True, db_column="status_id")
    code = models.CharField("Код", max_length=30, unique=True)
    name = models.CharField("Наименование", max_length=60, unique=True)
    sort_order = models.IntegerField("Порядок в жизненном цикле")
    is_final = models.BooleanField("Конечный статус", default=False)

    class Meta:
        db_table = "order_status"
        ordering = ["sort_order"]
        verbose_name = "статус заказа"
        verbose_name_plural = "статусы заказов"

    def __str__(self):
        return self.name


class ProductType(models.Model):
    id = models.AutoField(primary_key=True, db_column="product_type_id")
    name = models.CharField("Наименование", max_length=100, unique=True)

    class Meta:
        db_table = "product_type"
        ordering = ["name"]
        verbose_name = "вид продукции"
        verbose_name_plural = "виды продукции"

    def __str__(self):
        return self.name


class Material(models.Model):
    class Kind(models.TextChoices):
        PAPER = "paper", "Бумага"
        MEDIA = "media", "Носитель"

    id = models.AutoField(primary_key=True, db_column="material_id")
    name = models.CharField("Наименование", max_length=150, unique=True)
    kind = models.CharField("Тип", max_length=20, choices=Kind.choices)
    grammage = models.IntegerField("Плотность, г/м²", null=True, blank=True)
    is_active = models.BooleanField("Доступен для выбора", default=True)

    class Meta:
        db_table = "material"
        ordering = ["name"]
        verbose_name = "материал"
        verbose_name_plural = "материалы"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["paper", "media"]),
                name="material_kind_valid",
            ),
            models.CheckConstraint(
                condition=Q(grammage__isnull=True) | Q(grammage__gt=0),
                name="material_grammage_positive",
            ),
        ]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

class AppUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, login, password=None, **extra_fields):
        if not login:
            raise ValueError("Не указан логин")
        user = self.model(login=login, **extra_fields)
        user.set_password(password)  # хеш Argon2id с солью, пароль не хранится
        user.save(using=self._db)
        return user

    def create_superuser(self, login, password=None, **extra_fields):
        role, _ = Role.objects.get_or_create(
            code=RoleCode.ADMIN, defaults={"name": RoleCode.ADMIN.label}
        )
        extra_fields.setdefault("role", role)
        return self.create_user(login, password, **extra_fields)


class AppUser(AbstractBaseUser):
    """
    Пользователь системы (таблица app_user).
    Столбец пароля называется password_hash, как в физической модели.
    """

    id = models.AutoField(primary_key=True, db_column="user_id")
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, db_column="role_id",
        related_name="users", verbose_name="Роль",
    )
    login = models.CharField(
        "Логин", max_length=50, unique=True,
        validators=[MinLengthValidator(3)],
    )
    password = models.CharField("Хеш пароля", max_length=255, db_column="password_hash")
    full_name = models.CharField("ФИО", max_length=150)
    is_blocked = models.BooleanField("Вход запрещён", default=False)
    password_changed_at = models.DateTimeField(
        "Дата смены пароля", null=True, blank=True,
        help_text="Пусто — при входе требуется смена пароля",
    )

    # В физической модели нет столбца last_login — убираем его
    last_login = None

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS = ["full_name"]

    objects = AppUserManager()

    class Meta:
        db_table = "app_user"
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self):
        return f"{self.full_name} ({self.login})"

    # --- свойства, которые ожидает Django ---
    @property
    def is_active(self):
        return not self.is_blocked

    @property
    def is_admin(self):
        return self.role.code == RoleCode.ADMIN

    @property
    def is_staff(self):
        # доступ к встроенной админ-панели Django только у администратора
        return self.is_active and self.is_admin

    def has_perm(self, perm, obj=None):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.login


# ---------------------------------------------------------------------------
# Клиенты, заказы, тиражи
# ---------------------------------------------------------------------------

class Client(models.Model):
    class ClientType(models.TextChoices):
        LEGAL = "legal", "Юридическое лицо"
        PERSON = "person", "Физическое лицо"

    id = models.AutoField(primary_key=True, db_column="client_id")
    client_type = models.CharField("Тип клиента", max_length=10, choices=ClientType.choices)
    name = models.CharField("Наименование или ФИО", max_length=200)
    contact_person = models.CharField("Контактное лицо", max_length=150, null=True, blank=True)
    phone = models.CharField(
        "Телефон", max_length=30,
        validators=[RegexValidator(
            r"^[0-9+\-() ]+$",
            "Допустимы цифры и знаки + - ( ) и пробел",
        )],
    )
    email = models.EmailField("Email", max_length=100, null=True, blank=True)
    created_at = models.DateTimeField("Дата создания", db_default=Now(), editable=False)

    class Meta:
        db_table = "client"
        ordering = ["name"]
        verbose_name = "клиент"
        verbose_name_plural = "клиенты"
        indexes = [
            models.Index(fields=["name"], name="client_name_idx"),
            models.Index(fields=["phone"], name="client_phone_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(client_type__in=["legal", "person"]),
                name="client_type_valid",
            ),
        ]

    def __str__(self):
        return self.name


class Order(models.Model):
    id = models.AutoField(primary_key=True, db_column="order_id")
    order_number = models.CharField("Номер заказа", max_length=20, unique=True)
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, db_column="client_id",
        related_name="orders", verbose_name="Клиент",
    )
    manager = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_column="manager_id",
        related_name="managed_orders", verbose_name="Менеджер",
    )
    designer = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_column="designer_id",
        related_name="design_orders", verbose_name="Дизайнер",
        null=True, blank=True,
    )
    status = models.ForeignKey(
        OrderStatus, on_delete=models.PROTECT, db_column="status_id",
        related_name="orders", verbose_name="Статус",
    )
    created_at = models.DateTimeField("Дата создания", db_default=Now(), editable=False)
    due_date = models.DateField("Срок готовности")
    agreed_price = models.DecimalField(
        "Согласованная стоимость", max_digits=10, decimal_places=2, default=0,
    )
    layout_link = models.CharField("Ссылка на макет", max_length=500, null=True, blank=True)
    invoice_number = models.CharField("Номер накладной", max_length=30, null=True, blank=True)
    cancel_reason = models.CharField("Причина отмены", max_length=300, null=True, blank=True)
    row_version = models.IntegerField("Версия строки", default=1)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        indexes = [
            models.Index(fields=["due_date"], name="orders_due_date_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(agreed_price__gte=0),
                name="orders_price_nonnegative",
            ),
        ]

    def __str__(self):
        return self.order_number


class PrintRun(models.Model):
    id = models.AutoField(primary_key=True, db_column="run_id")
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, db_column="order_id",
        related_name="runs", verbose_name="Заказ",
    )
    product_type = models.ForeignKey(
        ProductType, on_delete=models.PROTECT, db_column="product_type_id",
        related_name="runs", verbose_name="Вид продукции",
    )
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, db_column="material_id",
        related_name="runs", verbose_name="Материал",
    )
    executor = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_column="executor_id",
        related_name="executor_runs", verbose_name="Исполнитель",
        null=True, blank=True,
    )
    format = models.CharField("Формат", max_length=50)
    quantity = models.IntegerField("Количество")
    produced_at = models.DateTimeField("Дата изготовления", null=True, blank=True)

    class Meta:
        db_table = "print_run"
        verbose_name = "тираж"
        verbose_name_plural = "тиражи"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1) & Q(quantity__lte=1000000),
                name="print_run_quantity_range",
            ),
        ]

    def __str__(self):
        return f"{self.order.order_number}: {self.product_type} {self.format} × {self.quantity}"


# ---------------------------------------------------------------------------
# Комментарии и журнал
# ---------------------------------------------------------------------------

class OrderComment(models.Model):
    class Kind(models.TextChoices):
        REGULAR = "regular", "Обычный"
        REMARKS = "remarks", "Замечания"
        APPROVAL = "approval", "Согласие"

    id = models.AutoField(primary_key=True, db_column="comment_id")
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, db_column="order_id",
        related_name="comments", verbose_name="Заказ",
    )
    author = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_column="author_id",
        related_name="comments", verbose_name="Автор",
    )
    kind = models.CharField("Вид", max_length=20, choices=Kind.choices, default=Kind.REGULAR)
    body = models.TextField("Текст")
    created_at = models.DateTimeField("Дата создания", db_default=Now(), editable=False)

    class Meta:
        db_table = "order_comment"
        ordering = ["created_at"]
        verbose_name = "комментарий"
        verbose_name_plural = "комментарии"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["regular", "remarks", "approval"]),
                name="order_comment_kind_valid",
            ),
            models.CheckConstraint(
                condition=Q(body__length__gte=1) & Q(body__length__lte=2000),
                name="order_comment_body_length",
            ),
        ]

    def __str__(self):
        return f"Комментарий к {self.order.order_number}"


class ActionLog(models.Model):
    id = models.AutoField(primary_key=True, db_column="log_id")
    user = models.ForeignKey(
        AppUser, on_delete=models.PROTECT, db_column="user_id",
        related_name="log_entries", verbose_name="Пользователь",
        null=True, blank=True,
    )
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, db_column="order_id",
        related_name="log_entries", verbose_name="Заказ",
        null=True, blank=True,
    )
    old_status = models.ForeignKey(
        OrderStatus, on_delete=models.PROTECT, db_column="old_status_id",
        related_name="+", verbose_name="Прежний статус",
        null=True, blank=True,
    )
    new_status = models.ForeignKey(
        OrderStatus, on_delete=models.PROTECT, db_column="new_status_id",
        related_name="+", verbose_name="Новый статус",
        null=True, blank=True,
    )
    action = models.CharField("Действие", max_length=50)
    details = models.CharField("Подробности", max_length=500, null=True, blank=True)
    created_at = models.DateTimeField("Дата и время", db_default=Now(), editable=False)

    class Meta:
        db_table = "action_log"
        ordering = ["-created_at"]
        verbose_name = "запись журнала"
        verbose_name_plural = "журнал действий"
        indexes = [
            models.Index(fields=["created_at"], name="action_log_created_at_idx"),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
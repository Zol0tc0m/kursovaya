from django.db import models
from django.contrib.auth.models import User

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer")
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    class Meta:
        db_table = "elshop_customer"


class CustomerProfile(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="profile")
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female")], blank=True, null=True)
    loyalty_points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Profile for {self.customer}"
    
    class Meta:
        db_table = "elshop_customer_profile"


class Address(models.Model):
    ADDRESS_TYPES = [
        ("billing", "Billing"),
        ("shipping", "Shipping"),
        ("other", "Other"),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ("customer", "type", "is_default")
        db_table = "elshop_address"


class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "elshop_supplier"


class Category(models.Model):
    name = models.CharField(max_length=200, unique=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "elshop_category"


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)  # новое поле
    categories = models.ManyToManyField(Category, related_name="products", blank=True)
    suppliers = models.ManyToManyField(Supplier, through="ProductSupplier", related_name="products")

    def __str__(self):
        return f"{self.name} ({self.sku})"

    class Meta:
        db_table = "elshop_product"


class ProductSupplier(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    supplier_sku = models.CharField(max_length=100, blank=True, null=True)
    lead_time_days = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        unique_together = ("product", "supplier")
        db_table = "elshop_product_supplier"


class Warehouse(models.Model):
    name = models.CharField(max_length=200, unique=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "elshop_warehouse"


class Inventory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.RESTRICT)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.RESTRICT)
    quantity = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    last_restocked = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("product", "warehouse")
        db_table = "elshop_inventory"


class Order(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("paid", "Paid"),
        ("shipped", "Shipped"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name="orders")
    billing_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, related_name="billing_orders")
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, related_name="shipping_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    currency = models.CharField(max_length=3, default="EUR")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "elshop_order"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.RESTRICT)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"
    
    class Meta:
        db_table = "elshop_order_item"


class Payment(models.Model):
    METHOD_CHOICES = [
        ("card", "Card"),
        ("bank_transfer", "Bank Transfer"),
        ("paypal", "PayPal"),
        ("cash", "Cash"),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    paid_at = models.DateTimeField(auto_now_add=True)
    transaction_ref = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = "elshop_payment"


class AuditLog(models.Model):
    table_name = models.CharField(max_length=100)
    operation = models.CharField(max_length=10)
    row_data = models.JSONField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = "elshop_audit_log"

class UserSettings(models.Model):
    THEME_CHOICES = [
        ("light", "Светлая"),
        ("dark", "Тёмная"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="light")

    def __str__(self):
        return f"Настройки {self.user.username}"

    class Meta:
        db_table = "elshop_user_settings"

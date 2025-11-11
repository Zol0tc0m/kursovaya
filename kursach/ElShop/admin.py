from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Customer, CustomerProfile, Address,
    Supplier, Category, Product, ProductSupplier,
    Warehouse, Inventory, Order, OrderItem, Payment,
    AuditLog
)

# ---------------------------
# Customer
# ---------------------------
class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    extra = 0

class AddressInline(admin.TabularInline):
    model = Address
    extra = 0

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "phone", "created_at")
    search_fields = ("email", "first_name", "last_name")
    inlines = [CustomerProfileInline, AddressInline]

# ---------------------------
# Supplier
# ---------------------------
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "phone")
    search_fields = ("name", "contact_email")

# ---------------------------
# Category
# ---------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)
    list_filter = ("parent",)

# ---------------------------
# Product
# ---------------------------
class ProductSupplierInline(admin.TabularInline):
    model = ProductSupplier
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "base_price", "active", "created_at", "image_tag")
    search_fields = ("name", "sku")
    list_filter = ("active", "categories")
    inlines = [ProductSupplierInline]
    filter_horizontal = ("categories",)  # только категории

    readonly_fields = ("image_preview",)  # только просмотр

    fieldsets = (
        (None, {
            "fields": ("name", "sku", "description", "base_price", "active", "categories")
        }),
        ("Изображение", {
            "fields": ("image", "image_preview")
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 150px;"/>', obj.image.url)
        return "-"
    image_preview.short_description = "Превью изображения"

    def image_tag(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:50px;"/>', obj.image.url)
        return "-"
    image_tag.short_description = "Изображение"

# ---------------------------
# Warehouse / Inventory
# ---------------------------
class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 1

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "location")
    search_fields = ("name",)
    inlines = [InventoryInline]

# ---------------------------
# Order / OrderItem
# ---------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "created_at", "total")
    search_fields = ("customer__email", "customer__first_name", "customer__last_name")
    list_filter = ("status", "created_at")
    inlines = [OrderItemInline]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount", "method", "paid_at")
    search_fields = ("order__id",)
    list_filter = ("method", "paid_at")

# ---------------------------
# Audit log
# ---------------------------
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("table_name", "operation", "changed_at", "changed_by")
    list_filter = ("table_name", "operation", "changed_at")
    search_fields = ("table_name", "changed_by")
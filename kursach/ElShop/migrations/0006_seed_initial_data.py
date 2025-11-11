from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_initial_data(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Customer = apps.get_model('ElShop', 'Customer')
    CustomerProfile = apps.get_model('ElShop', 'CustomerProfile')
    Address = apps.get_model('ElShop', 'Address')
    Supplier = apps.get_model('ElShop', 'Supplier')
    Category = apps.get_model('ElShop', 'Category')
    Product = apps.get_model('ElShop', 'Product')
    Warehouse = apps.get_model('ElShop', 'Warehouse')
    Inventory = apps.get_model('ElShop', 'Inventory')
    Order = apps.get_model('ElShop', 'Order')
    OrderItem = apps.get_model('ElShop', 'OrderItem')
    Payment = apps.get_model('ElShop', 'Payment')

    # --- Пользователь ---
    user, _ = User.objects.get_or_create(
        username='demo_user',
        defaults={
            'email': 'demo@example.com',
            'password': make_password('demo1234'),
            'is_staff': False,
        }
    )

    # --- Покупатель ---
    customer, _ = Customer.objects.get_or_create(
        user=user,
        email='demo@example.com',
        defaults={
            'first_name': 'Иван',
            'last_name': 'Покупатель',
            'phone': '+79001112233'
        }
    )

    CustomerProfile.objects.get_or_create(
        customer=customer,
        defaults={'gender': 'male', 'loyalty_points': 100}
    )

    # --- Поставщики ---
    supplier1, _ = Supplier.objects.get_or_create(name="TechImport", contact_email="info@techimport.com")
    supplier2, _ = Supplier.objects.get_or_create(name="GlobalElectro", contact_email="sales@globalelectro.com")

    # --- Категории ---
    cat_tv, _ = Category.objects.get_or_create(name="Телевизоры")
    cat_phone, _ = Category.objects.get_or_create(name="Смартфоны")
    cat_appliance, _ = Category.objects.get_or_create(name="Бытовая техника")

    # --- Продукты ---
    tv, _ = Product.objects.get_or_create(
        sku="TV-001",
        name="Samsung Smart TV 50\"",
        base_price=59999,
        description="Умный телевизор с 4K и Wi-Fi",
    )
    phone, _ = Product.objects.get_or_create(
        sku="PH-001",
        name="iPhone 15",
        base_price=99999,
        description="Флагманский смартфон Apple",
    )
    fridge, _ = Product.objects.get_or_create(
        sku="FR-001",
        name="LG Холодильник 300L",
        base_price=45999,
        description="Энергоэффективный холодильник",
    )

    tv.categories.add(cat_tv)
    phone.categories.add(cat_phone)
    fridge.categories.add(cat_appliance)

    tv.suppliers.add(supplier1)
    phone.suppliers.add(supplier2)
    fridge.suppliers.add(supplier1)

    # --- Склады ---
    wh1, _ = Warehouse.objects.get_or_create(name="Основной склад", location="Москва")
    wh2, _ = Warehouse.objects.get_or_create(name="Запасной склад", location="Санкт-Петербург")

    # --- Остатки ---
    Inventory.objects.get_or_create(product=tv, warehouse=wh1, defaults={'quantity': 10})
    Inventory.objects.get_or_create(product=phone, warehouse=wh1, defaults={'quantity': 15})
    Inventory.objects.get_or_create(product=fridge, warehouse=wh2, defaults={'quantity': 5})

    # --- Адрес ---
    addr, _ = Address.objects.get_or_create(
        customer=customer,
        type="shipping",
        line1="ул. Пушкина, дом 10",
        city="Москва",
        postal_code="101000",
        country="Россия",
        is_default=True
    )

    # --- Заказ ---
    order, _ = Order.objects.get_or_create(
        customer=customer,
        billing_address=addr,
        shipping_address=addr,
        status="paid",
        subtotal=105000,
        tax=5000,
        total=110000,
    )

    # --- Товары в заказе ---
    OrderItem.objects.get_or_create(order=order, product=tv, unit_price=59999, quantity=1, line_total=59999)
    OrderItem.objects.get_or_create(order=order, product=phone, unit_price=99999, quantity=1, line_total=99999)

    # --- Платёж ---
    Payment.objects.get_or_create(order=order, amount=110000, method="card")


def reverse_func(apps, schema_editor):
    # Ничего не делаем при откате
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ElShop', '0005_usersettings'),  # замени на последнюю миграцию
    ]

    operations = [
        migrations.RunPython(create_initial_data, reverse_func),
    ]
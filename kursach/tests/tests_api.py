import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from ElShop.models import Product, Category, Customer, Order, OrderItem, Payment


@pytest.mark.django_db
class TestAPI:
    def setup_method(self):
        """Создание базовых данных"""
        self.client = APIClient()
        self.user = User.objects.create_user(username='test', password='12345')
        self.category = Category.objects.create(name="Телевизоры")
        self.product = Product.objects.create(
            sku="SKU123",
            name="Samsung Smart TV",
            base_price=59999,
            description="Тестовый телевизор"
        )
        self.product.categories.add(self.category)
        self.customer = Customer.objects.create(
            user=self.user,
            email="user@example.com",
            first_name="Иван",
            last_name="Тестов"
        )

    def test_get_products_list(self):
        """API: получение списка товаров"""
        url = reverse('product-list')
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) >= 1
        assert response.data[0]["name"] == "Samsung Smart TV"

    def test_create_order(self):
        """API: создание заказа"""
        self.client.force_authenticate(user=self.user)
        url = reverse('order-list')
        data = {
            "customer": self.customer.id,
            "status": "paid",
            "subtotal": "59999.00",
            "tax": "0",
            "shipping_cost": "0",
            "total": "59999.00"
        }
        response = self.client.post(url, data, format='json')
        assert response.status_code in (200, 201)
        assert response.data["total"] == "59999.00"

    def test_create_payment(self):
        """API: создание платежа"""
        order_url = reverse('order-list')
        self.client.force_authenticate(user=self.user)
        order = self.client.post(order_url, {
            "customer": self.customer.id,
            "status": "paid",
            "subtotal": "1000",
            "tax": "0",
            "shipping_cost": "0",
            "total": "1000"
        }, format='json').data

        payment_url = reverse('payment-list')
        response = self.client.post(payment_url, {
            "order": order["id"],
            "amount": "1000",
            "method": "card"
        }, format='json')
        assert response.status_code in (200, 201)
        assert response.data["method"] == "card"

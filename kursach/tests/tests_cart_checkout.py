import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from ElShop.models import Product, Customer, Order


@pytest.mark.django_db
def test_add_to_cart_and_checkout(client):
    user = User.objects.create_user(username="demo", password="12345")
    client.login(username="demo", password="12345")
    customer = Customer.objects.create(user=user, email="demo@x.com", first_name="Demo", last_name="User")
    product = Product.objects.create(sku="T1", name="Тест товар", base_price=5000)

    # Добавление в корзину
    add_url = reverse("add_to_cart", args=[product.id])
    response = client.post(add_url)
    assert response.status_code == 302

    # Проверка содержимого корзины
    cart = client.session["cart"]
    assert str(product.id) in cart
    assert cart[str(product.id)]["quantity"] == 1

    # Оформление заказа
    checkout_url = reverse("checkout")
    response = client.post(checkout_url)
    assert response.status_code == 302  # редирект на success
    assert Order.objects.filter(customer=customer).exists()
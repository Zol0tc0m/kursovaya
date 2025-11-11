from locust import HttpUser, task, between

class ElShopUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Авторизация при запуске"""
        self.client.post("/login/", {"username": "testuser", "password": "12345"})

    @task(2)
    def view_catalog(self):
        """Просмотр каталога"""
        self.client.get("/api/products/")

    @task(1)
    def view_product(self):
        """Просмотр конкретного товара"""
        self.client.get("/api/products/1/")

    @task(1)
    def create_order(self):
        """Создание заказа"""
        payload = {
            "subtotal": 100,
            "total": 100,
            "status": "draft",
        }
        self.client.post("/api/orders/", json=payload)

    @task(1)
    def view_orders(self):
        """Просмотр заказов"""
        self.client.get("/api/orders/")

from django.shortcuts import redirect, render, get_object_or_404
from rest_framework import viewsets
from django.views import View
from django.views.generic import ListView
from .models import Customer, Product, Order, OrderItem, Payment, Category
from .serializers import (
    CustomerSerializer,
    ProductSerializer,
    OrderSerializer,
    OrderItemSerializer,
    PaymentSerializer,
)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

class ProductListView(ListView):
    model = Product
    template_name = "catalog.html"  # шаблон
    context_object_name = "products"
    paginate_by = 12  # показывать по 12 товаров на странице

    def get_queryset(self):
        qs = Product.objects.filter(active=True).prefetch_related("categories")

        # Фильтр по категории
        category_id = self.request.GET.get("category")
        if category_id:
            qs = qs.filter(categories__id=category_id)

        # Фильтр по цене
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        if min_price:
            try:
                qs = qs.filter(base_price__gte=float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                qs = qs.filter(base_price__lte=float(max_price))
            except ValueError:
                pass

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["selected_category"] = self.request.GET.get("category", "")
        context["min_price"] = self.request.GET.get("min_price", "")
        context["max_price"] = self.request.GET.get("max_price", "")
        return context

class AddToCartView(View):

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        cart = request.session.get("cart", {})

        if str(product.id) in cart:
            cart[str(product.id)]["quantity"] += 1
        else:
            cart[str(product.id)] = {
                "name": product.name,
                "price": float(product.base_price),
                "quantity": 1
            }

        request.session["cart"] = cart
        return redirect("catalog")  # возвращаемся на каталог


class CartView(View):
    template_name = "cart.html"

    def get(self, request):
        cart = request.session.get("cart", {})
        total = sum(item["price"] * item["quantity"] for item in cart.values())
        return render(request, self.template_name, {"cart": cart, "total": total})


class CheckoutView(View):
    template_name = "checkout.html"

    def get(self, request):
        cart = request.session.get("cart", {})
        total = sum(item["price"] * item["quantity"] for item in cart.values())
        return render(request, self.template_name, {"cart": cart, "total": total})

    def post(self, request):
        # Здесь можно создать Order и OrderItem из корзины
        cart = request.session.get("cart", {})
        if not cart:
            return redirect("catalog")

        # Простейший пример: создаём заказ для первого пользователя (или анонимного)
        from .models import Customer, Order, OrderItem

        customer = Customer.objects.first()  # TODO: заменить на реального пользователя
        order = Order.objects.create(customer=customer, status="draft", subtotal=0, tax=0, shipping_cost=0, total=0)

        subtotal = 0
        for pid, item in cart.items():
            line_total = item["price"] * item["quantity"]
            subtotal += line_total
            OrderItem.objects.create(
                order=order,
                product_id=int(pid),
                unit_price=item["price"],
                quantity=item["quantity"],
                discount=0,
                line_total=line_total
            )

        order.subtotal = subtotal
        order.total = subtotal  # Можно добавить налог и доставку позже
        order.save()

        # Очистим корзину
        request.session["cart"] = {}

        return redirect("checkout_success")


class CheckoutSuccessView(View):
    template_name = "checkout_success.html"

    def get(self, request):
        return render(request, self.template_name)
    
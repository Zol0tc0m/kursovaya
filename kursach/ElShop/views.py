from django.shortcuts import redirect, render, get_object_or_404
from rest_framework import viewsets
from django.views import View
from django.views.generic import ListView, DetailView
from .models import Customer, Product, Order, OrderItem, Payment, Category, Address, CustomerProfile
from .serializers import (
    CustomerSerializer,
    ProductSerializer,
    OrderSerializer,
    OrderItemSerializer,
    PaymentSerializer,
)
from django import forms
from django.db.models import Sum, F
from datetime import timedelta, date
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

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

class AddToCartView(LoginRequiredMixin, View):
    login_url = 'login'

    @login_required(login_url='login')
    def add_to_cart(request, product_id):
        product = get_object_or_404(Product, id=product_id)
        cart = request.session.get('cart', {})
        pid = str(product.id)
        if pid in cart:
            cart[pid]['quantity'] += 1
            cart[pid]['line_total'] = cart[pid]['price'] * cart[pid]['quantity']
        else:
            cart[pid] = {
                'name': product.name,
                'price': float(product.base_price),
                'quantity': 1,
                'line_total': float(product.base_price),
            }
        request.session['cart'] = cart
        return redirect('cart')

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


@method_decorator(login_required(login_url='login'), name='dispatch')
class CartView(View):
    def get(self, request):
        cart = request.session.get('cart', {})
        for pid, item in cart.items():
            if 'line_total' not in item:
                item['line_total'] = float(item['price']) * item['quantity']
        total = sum(item['line_total'] for item in cart.values())
        return render(request, 'cart.html', {'cart': cart, 'total': total})

@login_required(login_url='login')
def clear_cart(request):
    if request.method == "POST":
        # Полностью очищаем корзину
        request.session['cart'] = {}
        request.session.modified = True  # обязательно
        print("Cart cleared!")  # для логов
    return redirect('cart')

@login_required(login_url='login')
def update_cart(request):
    cart = request.session.get('cart', {})
    if request.method == 'POST':
        for pid, item in list(cart.items()):
            field_name = f'quantity_{pid}'
            if field_name in request.POST:
                try:
                    quantity = int(request.POST[field_name])
                    if quantity > 0:
                        item['quantity'] = quantity
                        item['line_total'] = float(item['price']) * quantity
                    else:
                        del cart[pid]
                except ValueError:
                    pass
        request.session['cart'] = cart
    return redirect('cart')


class CheckoutView(LoginRequiredMixin, View):
    login_url = 'login'
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
    
class ProductDetailView(DetailView):
    model = Product
    template_name = 'product_detail.html'
    context_object_name = 'product'

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Подтвердите пароль")

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'Пароли не совпадают')
        return cleaned_data


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            Customer.objects.create(
                user=user,
                email=user.email,
                first_name='',
                last_name=''
            )
            login(request, user)
            return redirect('catalog')
    else:
        form = RegisterForm()
    return render(request, 'auth/register.html', {'form': form})

@method_decorator(login_required(login_url='login'), name='dispatch')
class OrderHistoryView(View):
    def get(self, request):
        """
        Показываем все заказы текущего пользователя
        """
        try:
            customer = request.user.customer  # OneToOneField в Customer
        except AttributeError:
            # На случай, если Customer ещё не создан
            customer = None

        orders = Order.objects.filter(customer=customer) if customer else []
        return render(request, 'order_history.html', {'orders': orders})


@method_decorator(login_required(login_url='login'), name='dispatch')
class OrderDetailView(View):
    def get(self, request, order_id):
        """
        Подробности конкретного заказа
        """
        try:
            customer = request.user.customer
        except AttributeError:
            return redirect('catalog')  # если Customer нет, перенаправляем

        order = get_object_or_404(Order, id=order_id, customer=customer)
        items = order.items.all()
        return render(request, 'order_detail.html', {'order': order, 'items': items})
    
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'phone', 'email']

class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ['date_of_birth', 'gender']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['type', 'line1', 'city', 'country', 'is_default']

@method_decorator(login_required(login_url='login'), name='dispatch')
class ProfileView(View):
    template_name = 'profile.html'
    
    def get(self, request):
        try:
            customer = request.user.customer
            profile, created = CustomerProfile.objects.get_or_create(customer=customer)
            addresses = customer.addresses.all()
        except ObjectDoesNotExist:
            # Если у пользователя нет Customer, создаем его
            customer = Customer.objects.create(
                user=request.user,
                email=request.user.email,
                first_name='',
                last_name=''
            )
            profile, created = CustomerProfile.objects.get_or_create(customer=customer)
            addresses = []
        
        customer_form = CustomerForm(instance=customer)
        profile_form = CustomerProfileForm(instance=profile)
        address_form = AddressForm()
        
        context = {
            'customer': customer,
            'profile': profile,
            'addresses': addresses,
            'customer_form': customer_form,
            'profile_form': profile_form,
            'address_form': address_form,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        try:
            customer = request.user.customer
            profile, created = CustomerProfile.objects.get_or_create(customer=customer)
        except ObjectDoesNotExist:
            customer = Customer.objects.create(
                user=request.user,
                email=request.user.email,
                first_name='',
                last_name=''
            )
            profile, created = CustomerProfile.objects.get_or_create(customer=customer)
        
        # Обработка обновления основной информации
        if 'update_customer' in request.POST:
            customer_form = CustomerForm(request.POST, instance=customer)
            if customer_form.is_valid():
                customer_form.save()
                messages.success(request, 'Основная информация обновлена')
                return redirect('profile')
        
        # Обработка обновления профиля
        elif 'update_profile' in request.POST:
            profile_form = CustomerProfileForm(request.POST, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профиль обновлен')
                return redirect('profile')
        
        # Обработка добавления адреса
        elif 'add_address' in request.POST:
            address_form = AddressForm(request.POST)
            if address_form.is_valid():
                address = address_form.save(commit=False)
                address.customer = customer
                
                # Если адрес помечен как default, снимаем default с других адресов того же типа
                if address.is_default:
                    Address.objects.filter(
                        customer=customer, 
                        type=address.type
                    ).update(is_default=False)
                
                address.save()
                messages.success(request, 'Адрес добавлен')
                return redirect('profile')
        
        # Если формы не валидны, показываем с ошибками
        addresses = customer.addresses.all()
        customer_form = CustomerForm(instance=customer)
        profile_form = CustomerProfileForm(instance=profile)
        address_form = AddressForm()
        
        context = {
            'customer': customer,
            'profile': profile,
            'addresses': addresses,
            'customer_form': customer_form,
            'profile_form': profile_form,
            'address_form': address_form,
        }
        return render(request, self.template_name, context)
    
    # Функция проверки прав доступа
def admin_or_manager(user):
    return user.is_staff or user.groups.filter(name="Manager").exists()

@login_required(login_url='login')
@user_passes_test(admin_or_manager, login_url='catalog')  # если нет доступа — редирект в каталог
def analytics_view(request):
    today = timezone.now().date()
    last_week = today - timedelta(days=6)  # последние 7 дней включая сегодня

    # --- Гистограмма продаж по категориям ---
    category_sales = (
        OrderItem.objects
        .filter(order__status__in=['paid', 'shipped', 'completed'])
        .values('product__categories__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')
    )

    # --- Линейный график дохода за последнюю неделю ---
    daily_revenue = (
        Order.objects
        .filter(created_at__date__gte=last_week, status__in=['paid', 'shipped', 'completed'])
        .extra({'day': "date(created_at)"})
        .values('day')
        .annotate(total=Sum('total'))
        .order_by('day')
    )

    # --- Круговая диаграмма топ-5 товаров ---
    top_products = (
        OrderItem.objects
        .filter(order__status__in=['paid', 'shipped', 'completed'])
        .values('product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )

    context = {
        'category_sales': list(category_sales),
        'daily_revenue': list(daily_revenue),
        'top_products': list(top_products),
    }
    return render(request, 'analytics.html', context)
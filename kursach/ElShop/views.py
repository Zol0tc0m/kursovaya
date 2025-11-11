from django.shortcuts import redirect, render, get_object_or_404
from rest_framework import viewsets
from django.views import View
from django.views.generic import ListView, DetailView
from .models import Customer, Product, Order, OrderItem, Payment, Category, Address, CustomerProfile, UserSettings
from .serializers import (
    CustomerSerializer,
    ProductSerializer,
    OrderSerializer,
    OrderItemSerializer,
    PaymentSerializer,
)
from django import forms
from django.db.models import Sum
from django.db import transaction, IntegrityError
from datetime import timedelta
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
import csv


# --------- DRF viewsets ---------
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


# --------- Каталог ---------
class ProductListView(ListView):
    model = Product
    template_name = "catalog.html"
    context_object_name = "products"
    paginate_by = 12

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


# --------- Корзина ---------
class AddToCartView(LoginRequiredMixin, View):
    login_url = 'login'

    # поддержим и POST, и GET (на случай, если в шаблоне ссылка)
    def post(self, request, *args, **kwargs):
        return self._handle(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self._handle(request, *args, **kwargs)

    def _handle(self, request, *args, **kwargs):
        product_id = kwargs['product_id']              # <— берём из kwargs
        product = get_object_or_404(Product, id=product_id)

        cart = request.session.get('cart', {})
        pid = str(product.id)
        if pid in cart:
            cart[pid]['quantity'] += 1
            cart[pid]['line_total'] = float(cart[pid]['price']) * cart[pid]['quantity']
        else:
            cart[pid] = {
                'name': product.name,
                'price': float(product.base_price),
                'quantity': 1,
                'line_total': float(product.base_price),
            }
        request.session['cart'] = cart
        request.session.modified = True
        return redirect('cart')


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
        request.session['cart'] = {}
        request.session.modified = True
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


# --------- Checkout (адрес + способ оплаты, сохранение адреса у пользователя) ---------
class CheckoutView(LoginRequiredMixin, View):
    login_url = 'login'
    template_name = "checkout.html"

    def _norm(self, s: str) -> str:
        return (s or "").strip().lower()

    def get(self, request):
        cart = request.session.get("cart", {})
        total = sum(item["price"] * item["quantity"] for item in cart.values())
        method_choices = getattr(Payment, "METHOD_CHOICES", (
            ("card", "Card"),
            ("transfer", "Transfer"),
            ("mir", "MIR"),
            ("cash", "Cash"),
        ))
        return render(request, self.template_name, {
            "cart": cart,
            "total": total,
            "method_choices": method_choices,
            "posted": {},
        })

    def post(self, request):
        cart = request.session.get("cart", {})
        if not cart:
            messages.error(request, "Корзина пуста.")
            return redirect("catalog")

        # адрес и оплата из формы (ТОЛЬКО адрес, город, страна)
        line1 = (request.POST.get("line1") or "").strip()
        city = (request.POST.get("city") or "").strip()
        country = (request.POST.get("country") or "").strip()
        payment_method = (request.POST.get("payment_method") or "card").strip()

        required_missing = [name for name, val in [
            ("Адрес, строка 1", line1),
            ("Город", city),
            ("Страна", country),
        ] if not val]
        if required_missing:
            messages.error(request, "Заполните поля: " + ", ".join(required_missing))
            method_choices = getattr(Payment, "METHOD_CHOICES", (
                ("card", "Card"),
                ("transfer", "Transfer"),
                ("mir", "MIR"),
                ("cash", "Cash"),
            ))
            total = sum(item["price"] * item["quantity"] for item in cart.values())
            return render(request, self.template_name, {
                "cart": cart,
                "total": total,
                "method_choices": method_choices,
                "posted": request.POST,
            })

        try:
            with transaction.atomic():
                customer = request.user.customer

                # upsert адреса у пользователя (без второй строки и штата)
                existing = Address.objects.filter(
                    customer=customer,
                    line1__iexact=line1,
                    city__iexact=city,
                    country__iexact=country,
                ).first()

                if existing:
                    address = existing
                else:
                    address = Address.objects.create(
                        customer=customer,
                        line1=line1,
                        city=city,
                        country=country,
                        is_default=False,
                    )

                # создаём заказ
                order = Order.objects.create(
                    customer=customer,
                    shipping_address=address,
                    status="draft",
                    subtotal=0, tax=0, shipping_cost=0, total=0
                )

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
                order.total = subtotal
                order.status = "paid"  # или "processing"
                order.save()

                # платёж по выбранному способу
                Payment.objects.create(
                    order=order,
                    method=payment_method,
                    amount=subtotal,
                )

                # очистка корзины
                request.session["cart"] = {}
                request.session.modified = True

            messages.success(request, "✅ Заказ успешно оформлен.")
            return redirect("checkout_success")

        except IntegrityError:
            messages.error(request, "Ошибка при сохранении заказа. Изменения отменены.")
            return redirect("cart")
        except Exception as e:
            messages.error(request, f"Непредвиденная ошибка: {e}")
            return redirect("cart")


class CheckoutSuccessView(View):
    template_name = "checkout_success.html"

    def get(self, request):
        return render(request, self.template_name)


# --------- Товар ---------
class ProductDetailView(DetailView):
    model = Product
    template_name = 'product_detail.html'
    context_object_name = 'product'


# --------- Регистрация ---------
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


# --------- История заказов ---------
@method_decorator(login_required(login_url='login'), name='dispatch')
class OrderHistoryView(View):
    def get(self, request):
        try:
            customer = request.user.customer
        except AttributeError:
            customer = None

        orders = Order.objects.filter(customer=customer) if customer else []
        return render(request, 'order_history.html', {'orders': orders})


@method_decorator(login_required(login_url='login'), name='dispatch')
class OrderDetailView(View):
    def get(self, request, order_id):
        try:
            customer = request.user.customer
        except AttributeError:
            return redirect('catalog')

        order = get_object_or_404(Order, id=order_id, customer=customer)
        items = order.items.all()
        return render(request, 'order_detail.html', {'order': order, 'items': items})


# --------- Формы профиля (без AddressForm на добавление адреса) ---------
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


# --------- Профиль: только чтение адресов, сохранённых из заказов ---------
@method_decorator(login_required(login_url='login'), name='dispatch')
class ProfileView(View):
    template_name = 'profile.html'
    
    def get(self, request):
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            customer = Customer.objects.create(
                user=request.user,
                email=request.user.email,
                first_name='',
                last_name=''
            )
        profile, _ = CustomerProfile.objects.get_or_create(customer=customer)

        addresses = customer.addresses.all().order_by('-is_default', '-id')
        
        customer_form = CustomerForm(instance=customer)
        profile_form = CustomerProfileForm(instance=profile)
        
        context = {
            'customer': customer,
            'profile': profile,
            'addresses': addresses,
            'customer_form': customer_form,
            'profile_form': profile_form,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        try:
            customer = request.user.customer
        except ObjectDoesNotExist:
            customer = Customer.objects.create(
                user=request.user,
                email=request.user.email,
                first_name='',
                last_name=''
            )
        profile, _ = CustomerProfile.objects.get_or_create(customer=customer)
        
        if 'update_customer' in request.POST:
            customer_form = CustomerForm(request.POST, instance=customer)
            if customer_form.is_valid():
                customer_form.save()
                messages.success(request, 'Основная информация обновлена')
                return redirect('profile')
        
        elif 'update_profile' in request.POST:
            profile_form = CustomerProfileForm(request.POST, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профиль обновлён')
                return redirect('profile')
        
        addresses = customer.addresses.all().order_by('-is_default', '-id')
        customer_form = CustomerForm(instance=customer)
        profile_form = CustomerProfileForm(instance=profile)
        
        context = {
            'customer': customer,
            'profile': profile,
            'addresses': addresses,
            'customer_form': customer_form,
            'profile_form': profile_form,
        }
        return render(request, self.template_name, context)


# --------- Аналитика ---------
def admin_or_manager(user):
    return user.is_staff or user.groups.filter(name="Manager").exists()


@login_required(login_url='login')
@user_passes_test(admin_or_manager, login_url='catalog')
def analytics_view(request):
    today = timezone.now().date()
    last_week = today - timedelta(days=6)

    category_sales = (
        OrderItem.objects
        .filter(order__status__in=['paid', 'shipped', 'completed'])
        .values('product__categories__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')
    )

    daily_revenue = (
        Order.objects
        .filter(created_at__date__gte=last_week, status__in=['paid', 'shipped', 'completed'])
        .extra({'day': "date(created_at)"})
        .values('day')
        .annotate(total=Sum('total'))
        .order_by('day')
    )

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


@staff_member_required
def export_analytics_csv(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    orders = Order.objects.all()
    if start_date:
        orders = orders.filter(created_at__date__gte=start_date)
    if end_date:
        orders = orders.filter(created_at__date__lte=end_date)

    response = HttpResponse(content_type='text/csv; charset=cp1251')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'

    writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "Дата заказа", "ID заказа", "Статус", "Покупатель",
        "Сумма заказа", "Товар", "Количество", "Цена за единицу", "Сумма по товару"
    ])

    for order in orders:
        for item in order.items.all():
            writer.writerow([
                order.created_at.strftime("%Y-%m-%d %H:%M"),
                order.id,
                order.status,
                f"{order.customer.first_name} {order.customer.last_name}" if order.customer else "Аноним",
                float(order.total),
                item.product.name,
                item.quantity,
                float(item.unit_price),
                float(item.line_total)
            ])

    return response


def is_admin_or_manager(user):
    return user.is_staff or user.groups.filter(name='Manager').exists()


@user_passes_test(is_admin_or_manager)
def export_products_csv(request):
    response = HttpResponse(content_type='text/csv; charset=cp1251')
    response['Content-Disposition'] = 'attachment; filename="products_export.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['ID', 'Название', 'Описание', 'Цена', 'Категории'])

    for product in Product.objects.all().prefetch_related('categories'):
        categories = ', '.join(cat.name for cat in product.categories.all())
        writer.writerow([
            product.sku,
            product.name,
            product.description or '',
            str(product.base_price).replace('.', ','),
            categories
        ])

    return response


@user_passes_test(is_admin_or_manager)
def import_products_csv(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('cp1251').splitlines()
        reader = csv.DictReader(decoded_file, delimiter=';')

        imported = 0
        try:
            with transaction.atomic():
                for row in reader:
                    name = (row.get('Название') or '').strip()
                    if not name:
                        continue

                    description = (row.get('Описание') or '').strip()
                    price_str = (row.get('Цена') or '0').strip().replace(',', '.')
                    try:
                        base_price = float(price_str)
                    except ValueError:
                        raise ValueError(f"Неверный формат цены: {price_str}")

                    sku = row.get('ID') or f"SKU_{name[:5].upper()}_{imported+1}"

                    product, created = Product.objects.get_or_create(sku=sku, defaults={
                        'name': name,
                        'description': description,
                        'base_price': base_price,
                    })

                    if not created:
                        product.name = name
                        product.description = description
                        product.base_price = base_price
                        product.save()

                    cat_names = (row.get('Категории') or '').split(',')
                    product.categories.clear()
                    for cname in cat_names:
                        cname = cname.strip()
                        if cname:
                            cat, _ = Category.objects.get_or_create(name=cname)
                            product.categories.add(cat)

                    imported += 1

            messages.success(request, f'✅ Импортировано {imported} товаров.')
            return redirect('catalog')

        except Exception as e:
            messages.error(request, f'❌ Ошибка при импорте. Изменения отменены: {e}')
            return redirect('catalog')

    messages.error(request, '❌ Файл не выбран или имеет неверный формат.')
    return redirect('catalog')


@login_required
def toggle_theme(request):
    settings, _ = UserSettings.objects.get_or_create(user=request.user)
    new_theme = "dark" if settings.theme == "light" else "light"
    settings.theme = new_theme
    settings.save()
    return JsonResponse({"theme": new_theme})

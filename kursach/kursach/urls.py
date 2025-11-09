"""
URL configuration for kursach project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from ElShop.views import CustomerViewSet, ProductViewSet, OrderViewSet, OrderItemViewSet, PaymentViewSet, ProductListView, AddToCartView, CartView, CheckoutView, CheckoutSuccessView

router = DefaultRouter()
router.register(r"customers", CustomerViewSet)
router.register(r"products", ProductViewSet)
router.register(r"orders", OrderViewSet)
router.register(r"order-items", OrderItemViewSet)
router.register(r"payments", PaymentViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include(router.urls)),
    path("", ProductListView.as_view(), name="catalog"),
    path("cart/", CartView.as_view(), name="cart"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("checkout/success/", CheckoutSuccessView.as_view(), name="checkout_success"),
    path("add-to-cart/<int:product_id>/", AddToCartView.as_view(), name="add_to_cart"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
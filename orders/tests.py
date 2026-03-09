from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from django.urls import reverse
from django.utils import timezone

from coupons.models import Coupon
from orders.models import Order, OrderItem
from shop.models import Category, Product


@pytest.fixture
def category(db):
    category = Category()
    category.set_current_language("en")
    category.name = "Tea"
    category.slug = "tea"
    category.save()
    return category


@pytest.fixture
def product(db, category):
    product = Product()
    product.set_current_language("en")
    product.name = "Green Tea"
    product.slug = "green-tea"
    product.description = "Fresh green tea"
    product.category = category
    product.price = "9.99"
    product.available = True
    product.save()
    return Product.objects.get(pk=product.pk)


@pytest.fixture
def order(db):
    return Order.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        address="123 Main St",
        postal_code="12345",
        city="New York",
    )


@pytest.fixture
def order_with_items(order, product):
    OrderItem.objects.create(
        order=order,
        product=product,
        price=product.price,
        quantity=2,
    )
    return order


@pytest.fixture
def coupon(db):
    return Coupon.objects.create(
        code="SAVE10",
        valid_from=timezone.now() - timedelta(days=1),
        valid_to=timezone.now() + timedelta(days=1),
        discount=10,
        active=True,
    )


@pytest.mark.django_db
class TestOrderModel:
    def test_str(self, order):
        assert str(order) == f"Order {order.id}"

    def test_default_paid_is_false(self, order):
        assert order.paid is False

    def test_get_total_cost(self, order_with_items):
        assert order_with_items.get_total_cost() == Decimal("19.98")

    def test_get_total_cost_before_discount(self, order_with_items):
        assert order_with_items.get_total_cost_before_discount() == Decimal("19.98")

    def test_get_discount_without_coupon(self, order_with_items):
        assert order_with_items.get_discount() == Decimal("0")

    def test_get_discount_with_coupon(self, order_with_items, coupon):
        order_with_items.coupon = coupon
        order_with_items.discount = coupon.discount
        order_with_items.save()
        expected_discount = Decimal("19.98") * Decimal("10") / Decimal("100")
        assert order_with_items.get_discount() == expected_discount

    def test_get_total_cost_after_discount(self, order_with_items, coupon):
        order_with_items.coupon = coupon
        order_with_items.discount = coupon.discount
        order_with_items.save()
        expected = Decimal("19.98") - (Decimal("19.98") * Decimal("0.10"))
        assert order_with_items.get_total_cost() == expected

    def test_get_stripe_url_empty_without_id(self, order):
        assert order.get_stripe_url() == ""

    def test_get_stripe_url_with_test_key(self, order, settings):
        settings.STRIPE_SECRET_KEY = "sk_test_abc123"
        order.stripe_id = "pi_test_123"
        assert "/test/" in order.get_stripe_url()


@pytest.mark.django_db
class TestOrderItemModel:
    def test_str(self, order_with_items):
        item = order_with_items.items.first()
        assert str(item) == str(item.id)

    def test_get_cost(self, order_with_items):
        item = order_with_items.items.first()
        assert item.get_cost() == Decimal("19.98")


@pytest.mark.django_db
class TestOrderCreateView:
    def test_get_order_create_page(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 1, "override": False})
        url = reverse("orders:order_create")
        response = client.get(url)
        assert response.status_code == 200

    def test_post_creates_order(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 1, "override": False})
        url = reverse("orders:order_create")
        with patch("orders.views.order_created.delay"):
            response = client.post(
                url,
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "address": "123 Main St",
                    "postal_code": "12345",
                    "city": "New York",
                },
            )
        assert response.status_code == 302
        assert Order.objects.count() == 1

    def test_post_creates_order_items(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 2, "override": False})
        url = reverse("orders:order_create")
        with patch("orders.views.order_created.delay"):
            client.post(
                url,
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "address": "123 Main St",
                    "postal_code": "12345",
                    "city": "New York",
                },
            )
        order = Order.objects.first()
        assert order.items.count() == 1
        assert order.items.first().quantity == 2

    def test_post_clears_cart_after_order(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 1, "override": False})
        url = reverse("orders:order_create")
        with patch("orders.views.order_created.delay"):
            client.post(
                url,
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "address": "123 Main St",
                    "postal_code": "12345",
                    "city": "New York",
                },
            )
        assert "cart" not in client.session

    def test_post_with_coupon(self, client, product, coupon):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 1, "override": False})
        session = client.session
        session["coupon_id"] = coupon.id
        session.save()
        url = reverse("orders:order_create")
        with patch("orders.views.order_created.delay"):
            client.post(
                url,
                {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com",
                    "address": "123 Main St",
                    "postal_code": "12345",
                    "city": "New York",
                },
            )
        order = Order.objects.first()
        assert order.coupon == coupon
        assert order.discount == 10

    def test_invalid_form_does_not_create_order(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 1, "override": False})
        url = reverse("orders:order_create")
        response = client.post(url, {"first_name": "John"})
        assert response.status_code == 200
        assert Order.objects.count() == 0

from decimal import Decimal

import pytest

from django.urls import reverse

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
def product2(db, category):
    product = Product()
    product.set_current_language("en")
    product.name = "Black Tea"
    product.slug = "black-tea"
    product.description = "Rich black tea"
    product.category = category
    product.price = "7.99"
    product.available = True
    product.save()
    return Product.objects.get(pk=product.pk)


@pytest.mark.django_db
class TestCartAdd:
    def test_add_product_to_cart(self, client, product):
        url = reverse("cart:cart_add", args=[product.id])
        response = client.post(url, {"quantity": 1, "override": False})
        assert response.status_code == 302
        session = client.session
        cart_data = session["cart"]
        assert str(product.id) in cart_data
        assert cart_data[str(product.id)]["quantity"] == 1

    def test_add_product_increases_quantity(self, client, product):
        url = reverse("cart:cart_add", args=[product.id])
        client.post(url, {"quantity": 1, "override": False})
        client.post(url, {"quantity": 2, "override": False})
        cart_data = client.session["cart"]
        assert cart_data[str(product.id)]["quantity"] == 3

    def test_override_quantity(self, client, product):
        url = reverse("cart:cart_add", args=[product.id])
        client.post(url, {"quantity": 3, "override": False})
        client.post(url, {"quantity": 1, "override": True})
        cart_data = client.session["cart"]
        assert cart_data[str(product.id)]["quantity"] == 1

    def test_add_nonexistent_product_returns_404(self, client, db):
        url = reverse("cart:cart_add", args=[99999])
        response = client.post(url, {"quantity": 1, "override": False})
        assert response.status_code == 404

    def test_get_method_not_allowed(self, client, product):
        url = reverse("cart:cart_add", args=[product.id])
        response = client.get(url)
        assert response.status_code == 405


@pytest.mark.django_db
class TestCartRemove:
    def test_remove_product_from_cart(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 1, "override": False})
        remove_url = reverse("cart:cart_remove", args=[product.id])
        response = client.post(remove_url)
        assert response.status_code == 302
        cart_data = client.session["cart"]
        assert str(product.id) not in cart_data

    def test_get_method_not_allowed(self, client, product):
        url = reverse("cart:cart_remove", args=[product.id])
        response = client.get(url)
        assert response.status_code == 405


@pytest.mark.django_db
class TestCartDetail:
    def test_empty_cart_page(self, client, db):
        url = reverse("cart:cart_detail")
        response = client.get(url)
        assert response.status_code == 200

    def test_cart_shows_added_product(self, client, product):
        add_url = reverse("cart:cart_add", args=[product.id])
        client.post(add_url, {"quantity": 2, "override": False})
        response = client.get(reverse("cart:cart_detail"))
        assert "Green Tea" in response.content.decode()


@pytest.mark.django_db
class TestCartTotals:
    def test_total_price(self, client, product, product2):
        client.post(
            reverse("cart:cart_add", args=[product.id]),
            {"quantity": 2, "override": False},
        )
        client.post(
            reverse("cart:cart_add", args=[product2.id]),
            {"quantity": 1, "override": False},
        )
        # 9.99 * 2 + 7.99 * 1 = 27.97
        session = client.session
        cart_data = session["cart"]
        total = sum(
            Decimal(item["price"]) * item["quantity"] for item in cart_data.values()
        )
        assert total == Decimal("27.97")

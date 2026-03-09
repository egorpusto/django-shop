from unittest.mock import patch

import pytest

from django.urls import reverse

from .models import Category, Product


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
def unavailable_product(db, category):
    product = Product()
    product.set_current_language("en")
    product.name = "Unavailable Tea"
    product.slug = "unavailable-tea"
    product.description = ""
    product.category = category
    product.price = "5.00"
    product.available = False
    product.save()
    return product


@pytest.mark.django_db
class TestCategoryModel:
    def test_str(self, category):
        assert str(category) == "Tea"

    def test_get_absolute_url(self, category):
        url = category.get_absolute_url()
        assert url == reverse("shop:product_list_by_category", args=["tea"])


@pytest.mark.django_db
class TestProductModel:
    def test_str(self, product):
        assert str(product) == "Green Tea"

    def test_get_absolute_url(self, product):
        url = product.get_absolute_url()
        assert url == reverse("shop:product_detail", args=[product.id, "green-tea"])

    def test_available_default(self, product):
        assert product.available is True

    def test_price(self, product):
        from decimal import Decimal

        assert product.price == Decimal("9.99")


@pytest.mark.django_db
class TestProductListView:
    def test_product_list_status_code(self, client, product):
        url = reverse("shop:product_list")
        response = client.get(url)
        assert response.status_code == 200

    def test_product_list_contains_product(self, client, product):
        url = reverse("shop:product_list")
        response = client.get(url)
        assert "Green Tea" in response.content.decode()

    def test_unavailable_product_not_shown(self, client, unavailable_product):
        url = reverse("shop:product_list")
        response = client.get(url)
        assert "Unavailable Tea" not in response.content.decode()

    def test_product_list_by_category(self, client, product, category):
        url = reverse("shop:product_list_by_category", args=[category.slug])
        response = client.get(url)
        assert response.status_code == 200
        assert "Green Tea" in response.content.decode()

    def test_product_list_by_wrong_category(self, client, db):
        url = reverse("shop:product_list_by_category", args=["nonexistent"])
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestProductDetailView:
    def test_product_detail_status_code(self, client, product):
        url = reverse("shop:product_detail", args=[product.id, product.slug])
        with patch("shop.views.Recommender") as mock_recommender:
            mock_recommender.return_value.suggest_products_for.return_value = []
            response = client.get(url)
        assert response.status_code == 200

    def test_product_detail_contains_name(self, client, product):
        url = reverse("shop:product_detail", args=[product.id, product.slug])
        with patch("shop.views.Recommender") as mock_recommender:
            mock_recommender.return_value.suggest_products_for.return_value = []
            response = client.get(url)
        assert "Green Tea" in response.content.decode()

    def test_unavailable_product_returns_404(self, client, unavailable_product):
        url = reverse(
            "shop:product_detail",
            args=[unavailable_product.id, unavailable_product.slug],
        )
        with patch("shop.views.Recommender") as mock_recommender:
            mock_recommender.return_value.suggest_products_for.return_value = []
            response = client.get(url)
        assert response.status_code == 404

    def test_wrong_slug_returns_404(self, client, product):
        url = reverse("shop:product_detail", args=[product.id, "wrong-slug"])
        with patch("shop.views.Recommender") as mock_recommender:
            mock_recommender.return_value.suggest_products_for.return_value = []
            response = client.get(url)
        assert response.status_code == 404

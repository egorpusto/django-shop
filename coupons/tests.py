from datetime import timedelta

import pytest

from django.urls import reverse
from django.utils import timezone

from .models import Coupon


@pytest.fixture
def valid_coupon(db):
    return Coupon.objects.create(
        code="SAVE10",
        valid_from=timezone.now() - timedelta(days=1),
        valid_to=timezone.now() + timedelta(days=1),
        discount=10,
        active=True,
    )


@pytest.fixture
def expired_coupon(db):
    return Coupon.objects.create(
        code="EXPIRED",
        valid_from=timezone.now() - timedelta(days=10),
        valid_to=timezone.now() - timedelta(days=1),
        discount=15,
        active=True,
    )


@pytest.fixture
def inactive_coupon(db):
    return Coupon.objects.create(
        code="INACTIVE",
        valid_from=timezone.now() - timedelta(days=1),
        valid_to=timezone.now() + timedelta(days=1),
        discount=20,
        active=False,
    )


@pytest.mark.django_db
class TestCouponModel:
    def test_str(self, valid_coupon):
        assert str(valid_coupon) == "SAVE10"

    def test_discount_value(self, valid_coupon):
        assert valid_coupon.discount == 10

    def test_active_flag(self, valid_coupon, inactive_coupon):
        assert valid_coupon.active is True
        assert inactive_coupon.active is False


@pytest.mark.django_db
class TestCouponApplyView:
    def test_valid_coupon_applied(self, client, valid_coupon):
        url = reverse("coupons:apply")
        response = client.post(url, {"code": "SAVE10"})
        assert response.status_code == 302
        assert client.session["coupon_id"] == valid_coupon.id

    def test_expired_coupon_not_applied(self, client, expired_coupon):
        url = reverse("coupons:apply")
        response = client.post(url, {"code": "EXPIRED"})
        assert response.status_code == 302
        assert client.session.get("coupon_id") is None

    def test_inactive_coupon_not_applied(self, client, inactive_coupon):
        url = reverse("coupons:apply")
        response = client.post(url, {"code": "INACTIVE"})
        assert response.status_code == 302
        assert client.session.get("coupon_id") is None

    def test_nonexistent_coupon_not_applied(self, client, db):
        url = reverse("coupons:apply")
        response = client.post(url, {"code": "FAKECODE"})
        assert response.status_code == 302
        assert client.session.get("coupon_id") is None

    def test_case_insensitive_code(self, client, valid_coupon):
        url = reverse("coupons:apply")
        response = client.post(url, {"code": "save10"})
        assert response.status_code == 302
        assert client.session["coupon_id"] == valid_coupon.id

    def test_get_method_not_allowed(self, client, db):
        url = reverse("coupons:apply")
        response = client.get(url)
        assert response.status_code == 405

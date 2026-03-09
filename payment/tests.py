import json
from unittest.mock import MagicMock, patch

import pytest
from stripe import SignatureVerificationError

from django.urls import reverse

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


@pytest.mark.django_db
class TestPaymentProcessView:
    def test_get_renders_template(self, client, order):
        session = client.session
        session["order_id"] = order.id
        session.save()
        url = reverse("payment:process")
        response = client.get(url)
        assert response.status_code == 200

    def test_get_without_order_returns_404(self, client, db):
        session = client.session
        session["order_id"] = 99999
        session.save()
        url = reverse("payment:process")
        response = client.get(url)
        assert response.status_code == 404

    def test_post_redirects_to_stripe(self, client, order_with_items):
        session = client.session
        session["order_id"] = order_with_items.id
        session.save()
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/test"
        with patch(
            "payment.views.stripe.checkout.Session.create", return_value=mock_session
        ):
            url = reverse("payment:process")
            response = client.post(url)
        assert response.status_code == 302
        assert response["Location"] == "https://checkout.stripe.com/test"

    def test_post_without_order_returns_404(self, client, db):
        session = client.session
        session["order_id"] = 99999
        session.save()
        url = reverse("payment:process")
        response = client.post(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestPaymentCompletedView:
    def test_completed_page(self, client, db):
        url = reverse("payment:completed")
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestPaymentCanceledView:
    def test_canceled_page(self, client, db):
        url = reverse("payment:canceled")
        response = client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestStripeWebhook:
    def _make_event(self, order_id, payment_status="paid"):
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "payment",
                    "payment_status": payment_status,
                    "client_reference_id": str(order_id),
                    "payment_intent": "pi_test_123",
                }
            },
        }

    def test_valid_webhook_marks_order_paid(self, client, order_with_items):
        event = self._make_event(order_with_items.id)
        with patch(
            "stripe.Webhook.construct_event",
            return_value=MagicMock(
                type="checkout.session.completed",
                data=MagicMock(
                    object=MagicMock(
                        mode="payment",
                        payment_status="paid",
                        client_reference_id=str(order_with_items.id),
                        payment_intent="pi_test_123",
                    )
                ),
            ),
        ):
            with patch("payment.webhooks.payment_completed.delay"):
                with patch("payment.webhooks.Recommender"):
                    response = client.post(
                        reverse("stripe-webhook"),
                        data=json.dumps(event),
                        content_type="application/json",
                        HTTP_STRIPE_SIGNATURE="test_sig",
                    )
        assert response.status_code == 200
        order_with_items.refresh_from_db()
        assert order_with_items.paid is True
        assert order_with_items.stripe_id == "pi_test_123"

    def test_invalid_payload_returns_400(self, client, db):
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=ValueError("Invalid payload"),
        ):
            response = client.post(
                reverse("stripe-webhook"),
                data="bad payload",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test_sig",
            )
        assert response.status_code == 400

    def test_invalid_signature_returns_400(self, client, db):
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=SignatureVerificationError("Invalid signature", "sig_header"),
        ):
            response = client.post(
                reverse("stripe-webhook"),
                data="{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="bad_sig",
            )
        assert response.status_code == 400

    def test_order_not_found_returns_404(self, client, db):
        with patch(
            "stripe.Webhook.construct_event",
            return_value=MagicMock(
                type="checkout.session.completed",
                data=MagicMock(
                    object=MagicMock(
                        mode="payment",
                        payment_status="paid",
                        client_reference_id="99999",
                        payment_intent="pi_test_123",
                    )
                ),
            ),
        ):
            response = client.post(
                reverse("stripe-webhook"),
                data="{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test_sig",
            )
        assert response.status_code == 404
